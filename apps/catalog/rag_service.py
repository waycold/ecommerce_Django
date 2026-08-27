"""
apps/catalog/rag_service.py

RAG (Retrieval-Augmented Generation) service layer backing the internal
pgvector endpoints consumed by the Chatbot-Engine-Gateway microservice
(a sibling FastAPI project). These functions never call any embedding/LLM
API themselves -- the Gateway has already computed query vectors via Gemini
before calling in; Django's job is purely to run the pgvector similarity
search/CRUD against the catalog and the embedding-sync outbox queue.

Real similarity search runs through pgvector's `<=>` cosine-distance
operator (accelerated by the HNSW index on ItemEmbedding.vector) on
PostgreSQL in production. That operator does not exist on SQLite, which is
what the test suite runs against, so on any non-PostgreSQL backend an
equivalent pure-Python cosine similarity is computed over the same filtered
candidate set instead. This keeps all the *business logic* here (filtering,
ordering, similarity semantics, edge cases) fully unit-testable without a
live Postgres/pgvector connection, while production still gets the real
index-accelerated query. See vector_search_service / find_similar_items_service.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from django.db import connection, transaction
from django.utils import timezone

from pgvector.django import CosineDistance

from apps.catalog.models import (
    Item,
    ItemEmbedding,
    Category,
    Brand,
    EmbeddingSyncTask,
    build_embedding_text,
    EMBEDDING_DIM,
    EMBEDDING_MODEL_NAME,
)


# --- Internal helpers -------------------------------------------------------

def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Pure-Python cosine similarity in [-1, 1] (higher = more similar).

    Only used on backends without pgvector's `<=>` operator (i.e. SQLite,
    exercised by the test suite). PostgreSQL production traffic never hits
    this function -- it uses CosineDistance() so the HNSW index is used.
    """
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _serialize_item(item: Item, similarity: Optional[float] = None) -> Dict[str, Any]:
    data = {
        'id': item.id,
        'title': item.title,
        'slug': item.slug,
        'price': float(item.price),
        'stock': item.stock,
        'brand': item.brand.name if item.brand_id else None,
        'category': item.category.name if item.category_id else None,
        'description': item.description or '',
        'is_active': item.is_active,
    }
    if similarity is not None:
        data['similarity'] = similarity
    return data


def _apply_common_filters(
    qs,
    in_stock_only: bool = True,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
):
    if in_stock_only:
        qs = qs.filter(stock__gt=0)
    if min_price is not None:
        qs = qs.filter(price__gte=min_price)
    if max_price is not None:
        qs = qs.filter(price__lte=max_price)
    if category:
        qs = qs.filter(category__name__icontains=category)
    if brand:
        qs = qs.filter(brand__name__icontains=brand)
    return qs


def _rank_by_cosine_similarity(base_qs, reference_vector: List[float], top_k: int) -> List[Tuple[Item, float]]:
    """Runs the actual nearest-neighbour ranking of `base_qs` (an Item
    queryset already filtered down to candidates that have an embedding)
    against `reference_vector`, returning [(item, similarity), ...] sorted
    by similarity descending, capped at top_k.
    """
    results: List[Tuple[Item, float]] = []

    if connection.vendor == 'postgresql':
        # Neon uses PgBouncer in transaction-pooling mode: hnsw.ef_search
        # MUST be set via SET LOCAL inside this same transaction, never as
        # a session-level SET, or the setting would leak onto unrelated
        # requests that happen to reuse the same physical connection.
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL hnsw.ef_search = 60;")
            annotated = base_qs.annotate(
                distance=CosineDistance('embedding__vector', list(reference_vector))
            ).order_by('distance')[:top_k]
            for item in annotated:
                # pgvector cosine distance is in [0, 2] (0 = identical);
                # convert to a "higher = more similar" similarity score.
                results.append((item, round(1 - item.distance, 4)))
    else:
        # Non-PostgreSQL fallback (SQLite in tests): pgvector's `<=>`
        # operator doesn't exist here, so rank in Python instead.
        for item in base_qs:
            similarity = round(_cosine_similarity(item.embedding.vector, list(reference_vector)), 4)
            results.append((item, similarity))
        results.sort(key=lambda pair: pair[1], reverse=True)
        results = results[:top_k]

    return results


# --- 1. Vector search ---------------------------------------------------

def vector_search_service(
    query_vector: Optional[List[float]] = None,
    query_text: str = "",
    top_k: int = 8,
    in_stock_only: bool = True,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
) -> Tuple[Dict[str, Any], int]:
    """POST /api/v1/internal/catalog/vector-search/

    Runs pgvector cosine-similarity search over active items that already
    have a stored ItemEmbedding, applying the same filter conventions as
    the rest of this codebase's catalog search (category/brand:
    case-insensitive substring; price bounds inclusive; in_stock_only means
    stock > 0).
    """
    if not query_vector or not isinstance(query_vector, (list, tuple)):
        return {
            'error': 'Bad Request',
            'detail': 'query_vector is required and must be a non-empty list of floats.',
        }, 400

    if len(query_vector) != EMBEDDING_DIM:
        return {
            'error': 'Bad Request',
            'detail': f'query_vector must have exactly {EMBEDDING_DIM} dimensions, got {len(query_vector)}.',
        }, 400

    try:
        effective_top_k = max(1, min(int(top_k) if top_k is not None else 8, 50))
    except (TypeError, ValueError):
        return {'error': 'Bad Request', 'detail': 'top_k must be an integer.'}, 400

    base_qs = (
        Item.objects.filter(is_active=True, embedding__isnull=False)
        .select_related('category', 'brand', 'embedding')
    )
    base_qs = _apply_common_filters(base_qs, in_stock_only, min_price, max_price, category, brand)

    results = _rank_by_cosine_similarity(base_qs, query_vector, effective_top_k)
    items_data = [_serialize_item(item, similarity) for item, similarity in results]

    return {
        'status': 'success',
        'query': query_text or '',
        'top_k': effective_top_k,
        'count': len(items_data),
        'items': items_data,
        'engine': 'pgvector',
    }, 200


# --- 2. Similar items --------------------------------------------------

def find_similar_items_service(
    item_id: Any = None,
    top_k: int = 5,
    exclude_out_of_stock: bool = True,
) -> Tuple[Dict[str, Any], int]:
    """POST /api/v1/internal/catalog/embeddings/similar/

    Looks up the reference item's own stored embedding and finds its
    nearest neighbours (never including the reference item itself).

    Edge case design: an unknown item_id, or a reference item with no
    ItemEmbedding row yet, both return a 404 `{'error': ..., 'detail': ...}`
    payload -- matching this codebase's existing single-resource lookup
    convention (apps/catalog/views.py uses get_object_or_404 for
    slug/comment lookups; internal_views.py's own 400/405 error responses
    use this same {'error', 'detail'} shape). A quiet
    `{"status": "success", "items": []}` was considered but rejected: this
    is a "the referenced item doesn't exist / isn't embeddable" condition,
    not a legitimate empty result set, so it should surface as an error the
    Gateway can distinguish and log/retry on.
    """
    try:
        item_id_int = int(item_id)
    except (TypeError, ValueError):
        return {'error': 'Bad Request', 'detail': 'item_id must be an integer.'}, 400

    try:
        reference = Item.objects.select_related('embedding').get(pk=item_id_int)
    except Item.DoesNotExist:
        return {'error': 'Not Found', 'detail': f'Item {item_id_int} does not exist.'}, 404

    if not hasattr(reference, 'embedding'):
        return {'error': 'Not Found', 'detail': f'Item {item_id_int} has no embedding yet.'}, 404

    try:
        effective_top_k = max(1, min(int(top_k) if top_k is not None else 5, 50))
    except (TypeError, ValueError):
        return {'error': 'Bad Request', 'detail': 'top_k must be an integer.'}, 400

    base_qs = (
        Item.objects.filter(is_active=True, embedding__isnull=False)
        .exclude(pk=reference.pk)
        .select_related('category', 'brand', 'embedding')
    )
    if exclude_out_of_stock:
        base_qs = base_qs.filter(stock__gt=0)

    ref_vector = list(reference.embedding.vector)
    results = _rank_by_cosine_similarity(base_qs, ref_vector, effective_top_k)
    items_data = [_serialize_item(item, similarity) for item, similarity in results]

    return {
        'status': 'success',
        'reference_item_id': reference.id,
        'top_k': effective_top_k,
        'count': len(items_data),
        'items': items_data,
        'engine': 'pgvector',
    }, 200


# --- 3. Pending embedding tasks (claim-to-processing) -------------------

def get_pending_embedding_tasks_service(limit: int = 20) -> Tuple[Dict[str, Any], int]:
    """GET /api/v1/internal/catalog/embeddings/pending/

    Atomically claims up to `limit` PENDING tasks by flipping them to
    PROCESSING before returning them, so two overlapping Gateway poll
    cycles can never be handed the same task (standard outbox pattern).

    Claim algorithm (all inside one transaction.atomic() block):
      1. SELECT the oldest PENDING task ids, using SELECT ... FOR UPDATE
         SKIP LOCKED when the backend supports it (PostgreSQL in
         production) -- this makes a second, truly concurrent poll skip
         rows already locked by an in-flight first poll rather than
         blocking on or re-claiming them.
      2. UPDATE those specific ids to PROCESSING.
    SQLite (used in tests) doesn't support SELECT FOR UPDATE at all, so the
    lock step is skipped there; the plain filter(status=PENDING) ->
    update(status=PROCESSING) sequence is still race-free for *sequential*
    calls (which is what the test suite exercises), since the second call's
    filter(status=PENDING) simply won't see rows the first call already
    flipped to PROCESSING.
    """
    try:
        effective_limit = max(1, min(int(limit) if limit is not None else 20, 100))
    except (TypeError, ValueError):
        return {'error': 'Bad Request', 'detail': 'limit must be a positive integer.'}, 400

    with transaction.atomic():
        qs = EmbeddingSyncTask.objects.filter(status=EmbeddingSyncTask.Status.PENDING).order_by('created_at')

        if connection.features.has_select_for_update:
            lock_kwargs = {}
            if connection.features.has_select_for_update_skip_locked:
                lock_kwargs['skip_locked'] = True
            qs = qs.select_for_update(**lock_kwargs)

        claimed_ids = list(qs.values_list('pk', flat=True)[:effective_limit])

        if claimed_ids:
            EmbeddingSyncTask.objects.filter(pk__in=claimed_ids).update(
                status=EmbeddingSyncTask.Status.PROCESSING
            )

    tasks = (
        EmbeddingSyncTask.objects.filter(pk__in=claimed_ids)
        .select_related('item')
        .order_by('created_at')
    )

    task_data = [
        {
            'task_id': str(task.pk),
            'item_id': task.item_id,
            'text': build_embedding_text(task.item),
            'content_hash': task.content_hash,
        }
        for task in tasks
    ]

    return {
        'status': 'success',
        'count': len(task_data),
        'tasks': task_data,
    }, 200


# --- 4. Upsert embedding -------------------------------------------------

def upsert_embedding_service(
    item_id: Any = None,
    task_id: Any = None,
    vector: Optional[List[float]] = None,
    content_hash: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Tuple[Dict[str, Any], int]:
    """POST /api/v1/internal/catalog/embeddings/upsert/

    Creates or updates the ItemEmbedding row for item_id, then marks the
    referenced EmbeddingSyncTask as DONE. Defensive dimension validation is
    required here even though the Gateway already validates its own side --
    Django must not trust a client-supplied vector blindly.
    """
    if not vector or not isinstance(vector, (list, tuple)) or len(vector) != EMBEDDING_DIM:
        got = len(vector) if isinstance(vector, (list, tuple)) else 0
        return {
            'error': 'Bad Request',
            'detail': f'vector must be a list of exactly {EMBEDDING_DIM} floats, got {got}.',
        }, 400

    try:
        item_id_int = int(item_id)
    except (TypeError, ValueError):
        return {'error': 'Bad Request', 'detail': 'item_id must be an integer.'}, 400

    task_id_int = None
    if task_id is not None:
        try:
            task_id_int = int(task_id)
        except (TypeError, ValueError):
            return {'error': 'Bad Request', 'detail': 'task_id must be an integer.'}, 400

    try:
        item = Item.objects.get(pk=item_id_int)
    except Item.DoesNotExist:
        return {'error': 'Not Found', 'detail': f'Item {item_id_int} does not exist.'}, 404

    effective_model_name = model_name or EMBEDDING_MODEL_NAME

    ItemEmbedding.objects.update_or_create(
        item=item,
        defaults={
            'vector': list(vector),
            'content_hash': content_hash or '',
            'model_name': effective_model_name,
            'source_updated_at': timezone.now(),
        },
    )

    if task_id_int is not None:
        EmbeddingSyncTask.objects.filter(pk=task_id_int).update(status=EmbeddingSyncTask.Status.DONE)

    return {
        'status': 'success',
        'task_id': str(task_id) if task_id is not None else None,
        'item_id': item.id,
        'dimensions': len(vector),
        'model_name': effective_model_name,
        'content_hash': content_hash,
    }, 200


# --- 5. Mark embedding task as errored -----------------------------------

def mark_embedding_error_service(task_id: Any = None, error: Any = None) -> Tuple[Dict[str, Any], int]:
    """POST /api/v1/internal/catalog/embeddings/mark-error/

    Truncates the error message to 500 chars, matching both this field's
    max_length and the Gateway's own 500-char truncation so both sides
    agree on the limit.
    """
    if not task_id:
        return {'error': 'Bad Request', 'detail': 'task_id is required.'}, 400

    try:
        task_id_int = int(task_id)
    except (TypeError, ValueError):
        return {'error': 'Bad Request', 'detail': 'task_id must be an integer.'}, 400

    truncated_error = str(error or '')[:500]

    updated = EmbeddingSyncTask.objects.filter(pk=task_id_int).update(
        status=EmbeddingSyncTask.Status.ERROR,
        error_message=truncated_error,
    )

    if not updated:
        return {'error': 'Not Found', 'detail': f'EmbeddingSyncTask {task_id} does not exist.'}, 404

    return {'status': 'success', 'task_id': str(task_id), 'marked': 'error'}, 200


# --- 6. Verify items -------------------------------------------------------

def verify_items_service(
    item_ids: Optional[List[Any]] = None,
    slugs: Optional[List[Any]] = None,
) -> Tuple[Dict[str, Any], int]:
    """POST /api/v1/internal/catalog/items/verify/

    `not_found` echoes back the exact raw value the caller passed for
    anything that didn't resolve (a non-numeric item_id, an id with no
    match, or a slug with no exact case-sensitive match). Slugs are matched
    exactly against the stored slug -- never re-slugified -- so an
    identifier the catalog doesn't actually have comes back as not_found
    rather than being fuzzily resolved to a different product. An item
    reachable via both an id and a slug in the same request is deduped and
    appears only once in `items`.
    """
    item_ids = item_ids or []
    slugs = slugs or []

    if not item_ids and not slugs:
        return {
            'status': 'error',
            'error': 'Provide at least one of item_ids or slugs.',
        }, 400

    resolved: Dict[int, Item] = {}
    not_found: List[Any] = []

    if item_ids:
        # Map coerced int -> list of raw values that produced it, so a
        # miss can echo back every raw representation the caller sent.
        int_id_map: Dict[int, List[Any]] = {}
        for raw in item_ids:
            try:
                int_id = int(raw)
            except (TypeError, ValueError):
                not_found.append(raw)
                continue
            int_id_map.setdefault(int_id, []).append(raw)

        if int_id_map:
            found_ids = set()
            for item in Item.objects.filter(pk__in=int_id_map.keys()).select_related('category', 'brand'):
                resolved[item.id] = item
                found_ids.add(item.id)
            for int_id, raws in int_id_map.items():
                if int_id not in found_ids:
                    not_found.extend(raws)

    if slugs:
        found_slugs = set()
        for item in Item.objects.filter(slug__in=slugs).select_related('category', 'brand'):
            resolved[item.id] = item
            found_slugs.add(item.slug)
        for raw_slug in slugs:
            if raw_slug not in found_slugs:
                not_found.append(raw_slug)

    items_data = [_serialize_item(item) for item in resolved.values()]

    return {
        'status': 'success',
        'checked_at': timezone.now().isoformat(),
        'items': items_data,
        'not_found': not_found,
    }, 200


# --- 7. Catalog facets ------------------------------------------------------

def get_catalog_facets_service(facet: str = 'both') -> Tuple[Dict[str, Any], int]:
    """GET /api/v1/internal/catalog/facets/

    A facet can never offer a filter value that yields no hits: categories
    and brands returned here are restricted to ones with at least one
    currently-active item, not merely any row that exists in the
    Category/Brand tables.
    """
    normalized = (facet or 'both').strip().lower()
    if normalized not in ('category', 'brand', 'both'):
        return {
            'error': 'Bad Request',
            'detail': "facet must be one of 'category', 'brand', 'both'.",
        }, 400

    result: Dict[str, Any] = {'status': 'success', 'facet': normalized}

    if normalized in ('category', 'both'):
        result['categories'] = list(
            Category.objects.filter(items__is_active=True)
            .distinct()
            .order_by('name')
            .values_list('name', flat=True)
        )

    if normalized in ('brand', 'both'):
        result['brands'] = list(
            Brand.objects.filter(items__is_active=True)
            .distinct()
            .order_by('name')
            .values_list('name', flat=True)
        )

    return result, 200
