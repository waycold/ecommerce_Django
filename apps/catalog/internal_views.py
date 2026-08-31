"""
apps/catalog/internal_views.py

Internal API HTTP controllers for catalog searches, inventory health metrics,
review sentiment summaries, and semantic conceptual searches.
Secured by InternalSecretMiddleware and consumed by the AI orchestrator microservice.
"""

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from apps.catalog.services import (
    search_catalog_service,
    get_inventory_health_service,
    get_reviews_summary_service,
    semantic_catalog_search_service,
)
from apps.catalog.rag_service import (
    vector_search_service,
    find_similar_items_service,
    get_pending_embedding_tasks_service,
    upsert_embedding_service,
    mark_embedding_error_service,
    verify_items_service,
    get_catalog_facets_service,
)


def _parse_json_body(request):
    """Shared helper for the RAG endpoints below: parses the request body as
    JSON, returning (data, None) on success or (None, error_response) on
    failure -- mirrors the try/except json.loads pattern already used by
    catalog_semantic_search_view above.
    """
    try:
        body_content = request.body.decode('utf-8') if isinstance(request.body, bytes) else str(request.body)
        data = json.loads(body_content) if body_content else {}
        if not isinstance(data, dict):
            raise ValueError('Body must be a JSON object.')
        return data, None
    except Exception:
        return None, JsonResponse(
            {'error': 'Bad Request', 'detail': 'Invalid or missing JSON request body.'},
            status=400,
        )


def catalog_search_view(request):
    """
    GET /api/v1/internal/catalog/search/

    Query Parameters:
        - q (optional, str): Search query string.
        - category (optional, str/int): Filter by category ID or name.
        - limit (optional, int): Max products to return (default 10, max 50).

    Returns:
        JsonResponse: 200 with catalog search results, 400 on invalid params, 405 on invalid method.
    """
    if request.method != 'GET':
        return JsonResponse(
            {
                'error': 'Method Not Allowed',
                'detail': f'Method {request.method} not allowed. Must be GET.',
            },
            status=405,
        )

    q = request.GET.get('q', '').strip() or None
    category = request.GET.get('category', '').strip() or None
    limit_param = request.GET.get('limit')

    limit = 10
    if limit_param is not None:
        try:
            limit = int(limit_param)
            if limit <= 0:
                return JsonResponse(
                    {
                        'error': 'Bad Request',
                        'detail': 'Invalid limit parameter. Must be a positive integer.',
                    },
                    status=400,
                )
        except (ValueError, TypeError):
            return JsonResponse(
                {
                    'error': 'Bad Request',
                    'detail': 'Invalid limit parameter. Must be a positive integer.',
                },
                status=400,
            )

    results = search_catalog_service(
        query=q,
        category=category,
        limit=limit,
        request=request,
    )

    return JsonResponse(results, status=200)


def inventory_health_view(request):
    """
    GET /api/v1/internal/inventory/health/

    Query Parameters:
        - limit (optional, int): Max critical items to return (default 20, max 100).

    Returns:
        JsonResponse: 200 with inventory health, valuation, and critical stockout alerts.
    """
    if request.method != 'GET':
        return JsonResponse(
            {
                'error': 'Method Not Allowed',
                'detail': f'Method {request.method} not allowed. Must be GET.',
            },
            status=405,
        )

    limit_param = request.GET.get('limit', 20)
    try:
        limit = int(limit_param)
        if limit <= 0:
            return JsonResponse({'error': 'Bad Request', 'detail': 'Limit must be a positive integer.'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Bad Request', 'detail': 'Limit must be a positive integer.'}, status=400)

    result = get_inventory_health_service(limit=limit)
    return JsonResponse(result, status=200)


def catalog_reviews_summary_view(request):
    """
    GET /api/v1/internal/catalog/reviews-summary/

    Query Parameters:
        - item_id (optional, int): Filter by item ID
        - category (optional, str/int): Filter by category
        - brand (optional, str/int): Filter by brand
        - min_rating (optional, int): Minimum stars 1-5
        - max_rating (optional, int): Maximum stars 1-5
        - limit (optional, int): Max latest reviews (default 15, max 100)

    Returns:
        JsonResponse: 200 with review analytics, rating distributions, and sentiment feedback.
    """
    if request.method != 'GET':
        return JsonResponse(
            {
                'error': 'Method Not Allowed',
                'detail': f'Method {request.method} not allowed. Must be GET.',
            },
            status=405,
        )

    item_id = request.GET.get('item_id')
    category = request.GET.get('category')
    brand = request.GET.get('brand')
    min_rating = request.GET.get('min_rating')
    max_rating = request.GET.get('max_rating')
    limit_param = request.GET.get('limit', 15)

    try:
        limit = int(limit_param)
        if limit <= 0:
            return JsonResponse({'error': 'Bad Request', 'detail': 'Limit must be a positive integer.'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Bad Request', 'detail': 'Limit must be a positive integer.'}, status=400)

    result = get_reviews_summary_service(
        item_id=item_id,
        category=category,
        brand=brand,
        min_rating=min_rating,
        max_rating=max_rating,
        limit=limit,
    )
    return JsonResponse(result, status=200)


def catalog_semantic_search_view(request):
    """
    POST (or GET) /api/v1/internal/catalog/semantic-search/

    Request Body (POST) or Query Params (GET):
        - query_text (str): Free-form user/LLM shopping query
        - limit (optional, int): Max products to return (default 10, max 50)

    Returns:
        JsonResponse: 200 with intent-expanded search matches and semantic relevance ranks.
    """
    if request.method not in ('POST', 'GET'):
        return JsonResponse(
            {
                'error': 'Method Not Allowed',
                'detail': f'Method {request.method} not allowed. Must be POST or GET.',
            },
            status=405,
        )

    query_text = ""
    limit = 10

    if request.method == 'POST':
        try:
            body_content = request.body.decode('utf-8') if isinstance(request.body, bytes) else str(request.body)
            data = json.loads(body_content) if body_content else {}
            query_text = data.get('query_text') or data.get('q') or ""
            limit = data.get('limit', 10)
        except Exception:
            query_text = request.POST.get('query_text') or request.POST.get('q') or ""
            limit = request.POST.get('limit', 10)
    else:
        query_text = request.GET.get('query_text') or request.GET.get('q') or ""
        limit = request.GET.get('limit', 10)

    try:
        limit = int(limit)
        if limit <= 0:
            return JsonResponse({'error': 'Bad Request', 'detail': 'Limit must be a positive integer.'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Bad Request', 'detail': 'Limit must be a positive integer.'}, status=400)

    result = semantic_catalog_search_service(
        query_text=query_text,
        limit=limit,
        request=request,
    )
    return JsonResponse(result, status=200)


# ---------------------------------------------------------------------------
# RAG / pgvector Catalog Endpoints
# Consumed by the Chatbot-Engine-Gateway microservice to run real pgvector
# semantic search against this catalog. See apps/catalog/rag_service.py for
# all business logic -- these views are thin parse-and-delegate wrappers.
# ---------------------------------------------------------------------------

def catalog_vector_search_view(request):
    """
    POST /api/v1/internal/catalog/vector-search/

    Request Body (JSON):
        - query_vector (list[float], required): pre-computed embedding, must be EMBEDDING_DIM long.
        - query_text (str, optional): original user query text, echoed back.
        - top_k (int, optional): max results (default 8, clamped 1-50).
        - in_stock_only (bool, optional): only items with stock > 0 (default True).
        - min_price / max_price (float, optional): inclusive price bounds.
        - category / brand (str, optional): case-insensitive substring filters.

    Returns:
        JsonResponse: 200 with ranked items, 400 on invalid body/vector, 405 on invalid method.
    """
    if request.method != 'POST':
        return JsonResponse(
            {'error': 'Method Not Allowed', 'detail': f'Method {request.method} not allowed. Must be POST.'},
            status=405,
        )

    data, error_response = _parse_json_body(request)
    if error_response is not None:
        return error_response

    result, status_code = vector_search_service(
        query_vector=data.get('query_vector'),
        query_text=data.get('query_text', ''),
        top_k=data.get('top_k', 8),
        in_stock_only=data.get('in_stock_only', True),
        min_price=data.get('min_price'),
        max_price=data.get('max_price'),
        category=data.get('category'),
        brand=data.get('brand'),
    )
    return JsonResponse(result, status=status_code)


def catalog_embeddings_similar_view(request):
    """
    POST /api/v1/internal/catalog/embeddings/similar/

    Request Body (JSON):
        - item_id (int, required): reference item's id.
        - top_k (int, optional): max neighbours (default 5, clamped 1-50).
        - exclude_out_of_stock (bool, optional): default True.

    Returns:
        JsonResponse: 200 with nearest-neighbour items, 400 on bad item_id,
        404 if the item doesn't exist or has no embedding yet, 405 on invalid method.
    """
    if request.method != 'POST':
        return JsonResponse(
            {'error': 'Method Not Allowed', 'detail': f'Method {request.method} not allowed. Must be POST.'},
            status=405,
        )

    data, error_response = _parse_json_body(request)
    if error_response is not None:
        return error_response

    result, status_code = find_similar_items_service(
        item_id=data.get('item_id'),
        top_k=data.get('top_k', 5),
        exclude_out_of_stock=data.get('exclude_out_of_stock', True),
    )
    return JsonResponse(result, status=status_code)


def catalog_embeddings_pending_view(request):
    """
    GET /api/v1/internal/catalog/embeddings/pending/

    Query Parameters:
        - limit (optional, int): max tasks to claim (default 20, max 100).

    Atomically claims PENDING tasks by flipping them to PROCESSING before
    returning them, so two overlapping poll cycles never get the same task.

    Returns:
        JsonResponse: 200 with claimed tasks, 400 on invalid limit, 405 on invalid method.
    """
    if request.method != 'GET':
        return JsonResponse(
            {'error': 'Method Not Allowed', 'detail': f'Method {request.method} not allowed. Must be GET.'},
            status=405,
        )

    limit_param = request.GET.get('limit', 20)
    try:
        limit = int(limit_param)
        if limit <= 0:
            return JsonResponse({'error': 'Bad Request', 'detail': 'limit must be a positive integer.'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Bad Request', 'detail': 'limit must be a positive integer.'}, status=400)

    result, status_code = get_pending_embedding_tasks_service(limit=limit)
    return JsonResponse(result, status=status_code)


def catalog_embeddings_upsert_view(request):
    """
    POST /api/v1/internal/catalog/embeddings/upsert/

    Request Body (JSON):
        - item_id (int, required)
        - task_id (str, optional): EmbeddingSyncTask pk to mark DONE.
        - vector (list[float], required): must be exactly EMBEDDING_DIM long.
        - content_hash (str, optional)
        - model_name (str, optional): defaults to EMBEDDING_MODEL_NAME.

    Returns:
        JsonResponse: 200 on successful create/update, 400 on bad item_id/vector,
        404 if item_id doesn't exist, 405 on invalid method.
    """
    if request.method != 'POST':
        return JsonResponse(
            {'error': 'Method Not Allowed', 'detail': f'Method {request.method} not allowed. Must be POST.'},
            status=405,
        )

    data, error_response = _parse_json_body(request)
    if error_response is not None:
        return error_response

    result, status_code = upsert_embedding_service(
        item_id=data.get('item_id'),
        task_id=data.get('task_id'),
        vector=data.get('vector'),
        content_hash=data.get('content_hash'),
        model_name=data.get('model_name'),
    )
    return JsonResponse(result, status=status_code)


def catalog_embeddings_mark_error_view(request):
    """
    POST /api/v1/internal/catalog/embeddings/mark-error/

    Request Body (JSON):
        - task_id (str, required): EmbeddingSyncTask pk to mark ERROR.
        - error (str, required): human-readable message, truncated to 500 chars.

    Returns:
        JsonResponse: 200 on success, 400 if task_id missing, 404 if task_id
        doesn't exist, 405 on invalid method.
    """
    if request.method != 'POST':
        return JsonResponse(
            {'error': 'Method Not Allowed', 'detail': f'Method {request.method} not allowed. Must be POST.'},
            status=405,
        )

    data, error_response = _parse_json_body(request)
    if error_response is not None:
        return error_response

    result, status_code = mark_embedding_error_service(
        task_id=data.get('task_id'),
        error=data.get('error'),
    )
    return JsonResponse(result, status=status_code)


@csrf_exempt
def catalog_items_verify_view(request):
    """
    POST /api/v1/internal/catalog/items/verify/

    Request Body (JSON):
        - item_ids (list, optional): ids to verify (raw values echoed back in not_found on miss).
        - slugs (list[str], optional): slugs to verify, matched case-sensitively, never re-slugified.
        At least one of item_ids/slugs must be provided.

    Returns:
        JsonResponse: 200 with resolved items (deduped) + not_found raw values,
        400 (status: error shape) if neither item_ids nor slugs provided, 405 on invalid method.
    """
    if request.method != 'POST':
        return JsonResponse(
            {'error': 'Method Not Allowed', 'detail': f'Method {request.method} not allowed. Must be POST.'},
            status=405,
        )

    try:
        body_content = request.body.decode('utf-8') if isinstance(request.body, bytes) else str(request.body)
        data = json.loads(body_content) if body_content else {}
        if not isinstance(data, dict):
            raise ValueError('Body must be a JSON object.')
    except Exception:
        return JsonResponse({'status': 'error', 'error': 'Invalid or missing JSON request body.'}, status=400)

    result, status_code = verify_items_service(
        item_ids=data.get('item_ids'),
        slugs=data.get('slugs'),
    )
    return JsonResponse(result, status=status_code)


def catalog_facets_view(request):
    """
    GET /api/v1/internal/catalog/facets/

    Query Parameters:
        - facet (optional, str): 'category' | 'brand' | 'both' (default 'both').

    Returns:
        JsonResponse: 200 with categories/brands that have at least one active item,
        400 on invalid facet value, 405 on invalid method.
    """
    if request.method != 'GET':
        return JsonResponse(
            {'error': 'Method Not Allowed', 'detail': f'Method {request.method} not allowed. Must be GET.'},
            status=405,
        )

    facet = request.GET.get('facet', 'both')
    result, status_code = get_catalog_facets_service(facet=facet)
    return JsonResponse(result, status=status_code)
