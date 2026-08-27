"""
apps/catalog/test_rag_service.py

Tests for the Phase 3 RAG (pgvector) internal API service layer and views:
apps/catalog/rag_service.py, apps/catalog/internal_views.py (7 new RAG
endpoints), and the EmbeddingSyncTask model/outbox-claim behavior.

Runs entirely against SQLite (config.settings.testing). pgvector's `<=>`
cosine-distance operator does not exist on SQLite, so vector_search_service
and find_similar_items_service fall back to a pure-Python cosine similarity
ranking on this backend (see rag_service._rank_by_cosine_similarity) --
which is exactly what lets these tests assert real ordering/filtering
behavior without a live Postgres/pgvector connection. The PostgreSQL-only
`SET LOCAL hnsw.ef_search = 60` code path cannot be exercised here; it is a
code-presence/correctness-by-reading concern for the tech lead against real
Postgres, not something SQLite can verify.
"""

import hashlib
import json

from django.conf import settings
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import (
    Item,
    Category,
    Brand,
    Supplier,
    ItemEmbedding,
    EmbeddingSyncTask,
    EMBEDDING_DIM,
    build_embedding_text,
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


def _vector(active_index=None, value=1.0):
    """Builds an EMBEDDING_DIM-length vector of zeros, optionally with one
    component set to `value` at `active_index`."""
    v = [0.0] * EMBEDDING_DIM
    if active_index is not None:
        v[active_index] = value
    return v


class RagServiceFixtureMixin:
    """Shared catalog fixture: two similar 'Electronics' items, one
    unrelated 'Books' item, one inactive item (should never surface),
    and one item deliberately left without an embedding."""

    def _build_catalog(self):
        self.electronics = Category.objects.create(name="Electronics")
        self.books = Category.objects.create(name="Books")
        self.toys = Category.objects.create(name="Toys")

        self.sony = Brand.objects.create(name="Sony")
        self.generic = Brand.objects.create(name="Generic")
        self.zeta = Brand.objects.create(name="Zeta")

        self.supplier = Supplier.objects.create(name="Acme", country="USA")

        self.item_a = Item.objects.create(
            title="Wireless Headphones", description="Great sound", price=50, cost=20,
            stock=10, category=self.electronics, brand=self.sony, supplier=self.supplier,
        )
        self.item_b = Item.objects.create(
            title="Bluetooth Speaker", description="Loud and portable", price=80, cost=30,
            stock=0, category=self.electronics, brand=self.sony, supplier=self.supplier,
        )
        self.item_c = Item.objects.create(
            title="Mystery Novel", description="A thrilling read", price=15, cost=5,
            stock=5, category=self.books, brand=self.generic, supplier=self.supplier,
        )
        self.item_d_inactive = Item.objects.create(
            title="Discontinued Toy", price=9, cost=3, stock=3,
            category=self.toys, brand=self.zeta, supplier=self.supplier, is_active=False,
        )
        self.item_e_no_embedding = Item.objects.create(
            title="No Embedding Yet", price=25, cost=10, stock=1,
            category=self.electronics, brand=self.sony, supplier=self.supplier,
        )

        self.vec_a = _vector(0, 1.0)
        self.vec_b = _vector(0, 0.9)
        self.vec_b[1] = 0.1  # close to A, not identical
        self.vec_c = _vector(EMBEDDING_DIM - 1, 1.0)  # orthogonal to A/B
        self.vec_d = _vector(0, 1.0)  # would match the query if is_active weren't filtered

        now = timezone.now()
        ItemEmbedding.objects.create(item=self.item_a, vector=self.vec_a, content_hash="a" * 64, source_updated_at=now)
        ItemEmbedding.objects.create(item=self.item_b, vector=self.vec_b, content_hash="b" * 64, source_updated_at=now)
        ItemEmbedding.objects.create(item=self.item_c, vector=self.vec_c, content_hash="c" * 64, source_updated_at=now)
        ItemEmbedding.objects.create(item=self.item_d_inactive, vector=self.vec_d, content_hash="d" * 64, source_updated_at=now)

        self.query_vector = _vector(0, 1.0)  # identical to vec_a


class VectorSearchServiceTests(RagServiceFixtureMixin, TestCase):
    def setUp(self):
        self._build_catalog()

    def test_orders_by_similarity_and_excludes_inactive_and_unembedded(self):
        result, status = vector_search_service(
            query_vector=self.query_vector, query_text="headphones", top_k=8, in_stock_only=False,
        )
        self.assertEqual(status, 200)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['query'], 'headphones')
        self.assertEqual(result['engine'], 'pgvector')

        ids = [it['id'] for it in result['items']]
        self.assertNotIn(self.item_d_inactive.id, ids)       # inactive, even though vector matches
        self.assertNotIn(self.item_e_no_embedding.id, ids)   # no ItemEmbedding row at all
        self.assertEqual(ids, [self.item_a.id, self.item_b.id, self.item_c.id])

        sims = {it['id']: it['similarity'] for it in result['items']}
        self.assertAlmostEqual(sims[self.item_a.id], 1.0, places=4)
        self.assertGreater(sims[self.item_a.id], sims[self.item_b.id])
        self.assertGreater(sims[self.item_b.id], sims[self.item_c.id])
        self.assertAlmostEqual(sims[self.item_c.id], 0.0, places=4)

        # Verify shape of a serialized item matches the Gateway's contract.
        item_a_data = next(it for it in result['items'] if it['id'] == self.item_a.id)
        self.assertEqual(item_a_data['title'], "Wireless Headphones")
        self.assertEqual(item_a_data['slug'], self.item_a.slug)
        self.assertEqual(item_a_data['price'], 50.0)
        self.assertEqual(item_a_data['stock'], 10)
        self.assertEqual(item_a_data['brand'], "Sony")
        self.assertEqual(item_a_data['category'], "Electronics")

    def test_in_stock_only_excludes_out_of_stock_items(self):
        result, _ = vector_search_service(query_vector=self.query_vector, in_stock_only=True)
        ids = [it['id'] for it in result['items']]
        self.assertNotIn(self.item_b.id, ids)  # stock=0
        self.assertIn(self.item_a.id, ids)

    def test_price_bounds_are_inclusive(self):
        result, _ = vector_search_service(
            query_vector=self.query_vector, in_stock_only=False, min_price=50, max_price=80,
        )
        ids = {it['id'] for it in result['items']}
        self.assertEqual(ids, {self.item_a.id, self.item_b.id})  # boundary prices 50 and 80 both included

    def test_category_filter_is_case_insensitive_substring(self):
        result, _ = vector_search_service(query_vector=self.query_vector, in_stock_only=False, category="electr")
        ids = {it['id'] for it in result['items']}
        self.assertEqual(ids, {self.item_a.id, self.item_b.id})

    def test_brand_filter_is_case_insensitive_substring(self):
        result, _ = vector_search_service(query_vector=self.query_vector, in_stock_only=False, brand="SON")
        ids = {it['id'] for it in result['items']}
        self.assertIn(self.item_a.id, ids)
        self.assertNotIn(self.item_c.id, ids)

    def test_top_k_is_respected_and_clamped(self):
        result, _ = vector_search_service(query_vector=self.query_vector, in_stock_only=False, top_k=1)
        self.assertEqual(len(result['items']), 1)
        self.assertEqual(result['top_k'], 1)

    def test_missing_query_vector_returns_400(self):
        result, status = vector_search_service(query_vector=None)
        self.assertEqual(status, 400)
        self.assertIn('error', result)

    def test_wrong_dimension_query_vector_returns_400(self):
        result, status = vector_search_service(query_vector=[0.1, 0.2, 0.3])
        self.assertEqual(status, 400)


class SimilarItemsServiceTests(RagServiceFixtureMixin, TestCase):
    def setUp(self):
        self._build_catalog()

    def test_excludes_reference_item_and_orders_by_similarity(self):
        result, status = find_similar_items_service(item_id=self.item_a.id, top_k=5, exclude_out_of_stock=False)
        self.assertEqual(status, 200)
        self.assertEqual(result['reference_item_id'], self.item_a.id)

        ids = [it['id'] for it in result['items']]
        self.assertNotIn(self.item_a.id, ids)   # never includes the reference item itself
        self.assertEqual(ids[0], self.item_b.id)  # closest neighbour among the rest

    def test_exclude_out_of_stock_defaults_to_true(self):
        result, _ = find_similar_items_service(item_id=self.item_a.id)
        ids = [it['id'] for it in result['items']]
        self.assertNotIn(self.item_b.id, ids)  # stock=0, excluded by default

    def test_reference_item_without_embedding_returns_404_not_empty_success(self):
        result, status = find_similar_items_service(item_id=self.item_e_no_embedding.id)
        self.assertEqual(status, 404)
        self.assertIn('error', result)
        self.assertIn('detail', result)

    def test_nonexistent_item_id_returns_404(self):
        result, status = find_similar_items_service(item_id=999999)
        self.assertEqual(status, 404)

    def test_non_integer_item_id_returns_400(self):
        result, status = find_similar_items_service(item_id="not-a-number")
        self.assertEqual(status, 400)


class PendingEmbeddingTasksClaimTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Electronics")
        brand = Brand.objects.create(name="Sony")
        supplier = Supplier.objects.create(name="Acme", country="USA")
        self.items = [
            Item.objects.create(
                title=f"Item {i}", price=10, cost=5, stock=1,
                category=category, brand=brand, supplier=supplier,
            )
            for i in range(3)
        ]
        self.tasks = []
        for item in self.items:
            content_hash = hashlib.sha256(build_embedding_text(item).encode("utf-8")).hexdigest()
            self.tasks.append(EmbeddingSyncTask.objects.create(item=item, content_hash=content_hash))

    def test_claim_flips_status_and_second_poll_never_sees_same_task(self):
        result1, status1 = get_pending_embedding_tasks_service(limit=2)
        self.assertEqual(status1, 200)
        self.assertEqual(result1['count'], 2)
        claimed_ids_1 = {t['task_id'] for t in result1['tasks']}

        # The claimed tasks are now PROCESSING, not PENDING, in the DB.
        self.assertEqual(
            EmbeddingSyncTask.objects.filter(status=EmbeddingSyncTask.Status.PROCESSING).count(), 2,
        )
        self.assertEqual(
            EmbeddingSyncTask.objects.filter(status=EmbeddingSyncTask.Status.PENDING).count(), 1,
        )

        result2, status2 = get_pending_embedding_tasks_service(limit=10)
        self.assertEqual(status2, 200)
        claimed_ids_2 = {t['task_id'] for t in result2['tasks']}

        # No overlap between the two claim batches: a second overlapping
        # poll cycle can never be handed an already-claimed task.
        self.assertEqual(claimed_ids_1 & claimed_ids_2, set())
        self.assertEqual(result2['count'], 1)  # only the 3rd task was still pending

        # A third poll finds nothing left to claim.
        result3, status3 = get_pending_embedding_tasks_service(limit=10)
        self.assertEqual(result3['count'], 0)

    def test_task_payload_text_and_hash_are_correct(self):
        result, _ = get_pending_embedding_tasks_service(limit=1)
        task_data = result['tasks'][0]
        item = self.items[0]
        self.assertEqual(task_data['task_id'], str(self.tasks[0].pk))
        self.assertEqual(task_data['item_id'], item.id)
        self.assertEqual(task_data['text'], build_embedding_text(item))
        self.assertEqual(task_data['content_hash'], self.tasks[0].content_hash)

    def test_invalid_limit_returns_400(self):
        result, status = get_pending_embedding_tasks_service(limit="not-a-number")
        self.assertEqual(status, 400)


class UpsertEmbeddingServiceTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Electronics")
        brand = Brand.objects.create(name="Sony")
        supplier = Supplier.objects.create(name="Acme", country="USA")
        self.item = Item.objects.create(
            title="Widget", price=10, cost=5, stock=1, category=category, brand=brand, supplier=supplier,
        )
        self.content_hash = hashlib.sha256(build_embedding_text(self.item).encode("utf-8")).hexdigest()
        self.task = EmbeddingSyncTask.objects.create(item=self.item, content_hash=self.content_hash)

    def test_creates_embedding_and_marks_task_done(self):
        vector = [0.5] * EMBEDDING_DIM
        result, status = upsert_embedding_service(
            item_id=self.item.id, task_id=str(self.task.pk), vector=vector,
            content_hash=self.content_hash, model_name="test-model",
        )
        self.assertEqual(status, 200)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['task_id'], str(self.task.pk))
        self.assertEqual(result['item_id'], self.item.id)
        self.assertEqual(result['dimensions'], EMBEDDING_DIM)
        self.assertEqual(result['model_name'], 'test-model')

        embedding = ItemEmbedding.objects.get(item=self.item)
        self.assertEqual(len(embedding.vector), EMBEDDING_DIM)
        self.assertEqual(embedding.model_name, 'test-model')

        self.task.refresh_from_db()
        self.assertEqual(self.task.status, EmbeddingSyncTask.Status.DONE)

    def test_upsert_updates_existing_embedding_without_duplicating(self):
        upsert_embedding_service(
            item_id=self.item.id, task_id=str(self.task.pk),
            vector=[0.1] * EMBEDDING_DIM, content_hash="x" * 64,
        )
        upsert_embedding_service(
            item_id=self.item.id, task_id=str(self.task.pk),
            vector=[0.9] * EMBEDDING_DIM, content_hash="y" * 64,
        )

        self.assertEqual(ItemEmbedding.objects.filter(item=self.item).count(), 1)
        embedding = ItemEmbedding.objects.get(item=self.item)
        self.assertAlmostEqual(embedding.vector[0], 0.9, places=4)
        self.assertEqual(embedding.content_hash, "y" * 64)

    def test_wrong_dimension_vector_returns_400(self):
        result, status = upsert_embedding_service(
            item_id=self.item.id, task_id=str(self.task.pk), vector=[0.1, 0.2],
        )
        self.assertEqual(status, 400)
        self.assertFalse(ItemEmbedding.objects.filter(item=self.item).exists())

    def test_nonexistent_item_returns_404(self):
        result, status = upsert_embedding_service(
            item_id=999999, task_id=str(self.task.pk), vector=[0.1] * EMBEDDING_DIM,
        )
        self.assertEqual(status, 404)

    def test_malformed_task_id_returns_400_not_500(self):
        # Regression: filter(pk=task_id) used to reach the DB with an
        # un-coerced task_id and raise an uncaught ValueError (-> 500) for
        # anything the ORM couldn't cast to an int.
        for bad_task_id in ("not-a-number", [1, 2], {"a": 1}, ""):
            with self.subTest(bad_task_id=bad_task_id):
                result, status = upsert_embedding_service(
                    item_id=self.item.id, task_id=bad_task_id, vector=[0.1] * EMBEDDING_DIM,
                )
                self.assertEqual(status, 400)
                self.assertEqual(result['error'], 'Bad Request')
                # The embedding write itself must not have happened either.
                self.assertFalse(ItemEmbedding.objects.filter(item=self.item).exists())


class MarkEmbeddingErrorServiceTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Electronics")
        brand = Brand.objects.create(name="Sony")
        supplier = Supplier.objects.create(name="Acme", country="USA")
        item = Item.objects.create(
            title="Widget", price=10, cost=5, stock=1, category=category, brand=brand, supplier=supplier,
        )
        self.task = EmbeddingSyncTask.objects.create(item=item, content_hash="a" * 64)

    def test_marks_error_and_truncates_message_to_500_chars(self):
        long_error = "x" * 600
        result, status = mark_embedding_error_service(task_id=str(self.task.pk), error=long_error)
        self.assertEqual(status, 200)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['task_id'], str(self.task.pk))
        self.assertEqual(result['marked'], 'error')

        self.task.refresh_from_db()
        self.assertEqual(self.task.status, EmbeddingSyncTask.Status.ERROR)
        self.assertEqual(len(self.task.error_message), 500)
        self.assertEqual(self.task.error_message, "x" * 500)

    def test_missing_task_id_returns_400(self):
        result, status = mark_embedding_error_service(task_id=None, error="oops")
        self.assertEqual(status, 400)

    def test_nonexistent_task_id_returns_404(self):
        result, status = mark_embedding_error_service(task_id="999999", error="oops")
        self.assertEqual(status, 404)

    def test_malformed_task_id_returns_400_not_500(self):
        # Regression: filter(pk=task_id) used to reach the DB with an
        # un-coerced task_id and raise an uncaught ValueError (-> 500) for
        # anything the ORM couldn't cast to an int.
        for bad_task_id in ("not-a-number", [1, 2], {"a": 1}):
            with self.subTest(bad_task_id=bad_task_id):
                result, status = mark_embedding_error_service(task_id=bad_task_id, error="oops")
                self.assertEqual(status, 400)
                self.assertEqual(result['error'], 'Bad Request')


class VerifyItemsServiceTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Electronics")
        brand = Brand.objects.create(name="Sony")
        supplier = Supplier.objects.create(name="Acme", country="USA")
        self.item_a = Item.objects.create(
            title="Widget A", price=10, cost=5, stock=1, category=category, brand=brand,
            supplier=supplier, slug="widget-a",
        )
        self.item_b = Item.objects.create(
            title="Widget B", price=20, cost=8, stock=2, category=category, brand=brand,
            supplier=supplier, slug="widget-b",
        )

    def test_resolves_by_id_and_slug_and_echoes_raw_not_found_values(self):
        result, status = verify_items_service(
            item_ids=[self.item_a.id, 999999, "abc"],
            slugs=[self.item_b.slug, "does-not-exist-slug"],
        )
        self.assertEqual(status, 200)
        self.assertEqual(result['status'], 'success')
        self.assertIn('checked_at', result)

        ids = {it['id'] for it in result['items']}
        self.assertEqual(ids, {self.item_a.id, self.item_b.id})
        self.assertEqual(len(result['items']), 2)

        # Raw values are echoed back verbatim -- not coerced/normalized.
        self.assertEqual(
            set(map(str, result['not_found'])),
            {'abc', '999999', 'does-not-exist-slug'},
        )

    def test_slug_lookup_is_case_sensitive_never_fuzzily_resolved(self):
        result, status = verify_items_service(slugs=[self.item_a.slug.upper()])
        self.assertEqual(status, 200)
        self.assertEqual(result['items'], [])
        self.assertIn(self.item_a.slug.upper(), result['not_found'])

    def test_dedup_when_same_item_reachable_by_both_id_and_slug(self):
        result, status = verify_items_service(item_ids=[self.item_a.id], slugs=[self.item_a.slug])
        self.assertEqual(status, 200)
        self.assertEqual(len(result['items']), 1)
        self.assertEqual(result['not_found'], [])

    def test_missing_both_item_ids_and_slugs_returns_400_error_shape(self):
        result, status = verify_items_service(item_ids=None, slugs=None)
        self.assertEqual(status, 400)
        self.assertEqual(result['status'], 'error')
        self.assertIn('error', result)


class CatalogFacetsServiceTests(TestCase):
    def setUp(self):
        self.electronics = Category.objects.create(name="Electronics")
        self.books = Category.objects.create(name="Books")
        self.toys = Category.objects.create(name="Toys")  # only ever reachable via an inactive item

        self.sony = Brand.objects.create(name="Sony")
        self.generic = Brand.objects.create(name="Generic")
        self.zeta = Brand.objects.create(name="Zeta")  # only ever reachable via an inactive item

        supplier = Supplier.objects.create(name="Acme", country="USA")

        Item.objects.create(title="A", price=10, cost=5, stock=1, category=self.electronics, brand=self.sony, supplier=supplier, is_active=True)
        Item.objects.create(title="B", price=10, cost=5, stock=1, category=self.books, brand=self.generic, supplier=supplier, is_active=True)
        Item.objects.create(title="C", price=10, cost=5, stock=1, category=self.toys, brand=self.zeta, supplier=supplier, is_active=False)

    def test_both_facets_exclude_values_with_no_active_item(self):
        result, status = get_catalog_facets_service(facet="both")
        self.assertEqual(status, 200)
        self.assertEqual(result['categories'], ["Books", "Electronics"])
        self.assertEqual(result['brands'], ["Generic", "Sony"])

    def test_category_only_omits_brands_key(self):
        result, _ = get_catalog_facets_service(facet="category")
        self.assertIn('categories', result)
        self.assertNotIn('brands', result)

    def test_brand_only_omits_categories_key(self):
        result, _ = get_catalog_facets_service(facet="brand")
        self.assertIn('brands', result)
        self.assertNotIn('categories', result)

    def test_invalid_facet_value_returns_400(self):
        result, status = get_catalog_facets_service(facet="invalid")
        self.assertEqual(status, 400)

    def test_default_facet_is_both(self):
        result, _ = get_catalog_facets_service()
        self.assertEqual(result['facet'], 'both')


class RagInternalViewsWiringTests(TestCase):
    """End-to-end checks through the real URL + InternalSecretMiddleware
    stack, proving routing/method/JSON-parsing wiring on top of the
    thorough service-level tests above (which is where the actual business
    logic is exercised)."""

    def setUp(self):
        self.client = Client()
        self.auth_headers = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}

        category = Category.objects.create(name="Electronics")
        brand = Brand.objects.create(name="Sony")
        supplier = Supplier.objects.create(name="Acme", country="USA")
        self.item = Item.objects.create(
            title="Widget", price=10, cost=5, stock=1, category=category, brand=brand, supplier=supplier,
        )
        ItemEmbedding.objects.create(
            item=self.item, vector=_vector(0, 1.0), content_hash="a" * 64, source_updated_at=timezone.now(),
        )

    def test_vector_search_end_to_end_success(self):
        response = self.client.post(
            reverse('internal:internal_catalog_vector_search'),
            data=json.dumps({'query_vector': _vector(0, 1.0), 'query_text': 'widget'}),
            content_type='application/json',
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'success')
        self.assertEqual(body['count'], 1)

    def test_missing_secret_header_is_rejected_by_middleware(self):
        response = self.client.get(reverse('internal:internal_catalog_facets'))
        self.assertEqual(response.status_code, 401)

    def test_items_verify_rejects_get_method(self):
        response = self.client.get(reverse('internal:internal_catalog_items_verify'), **self.auth_headers)
        self.assertEqual(response.status_code, 405)

    def test_items_verify_missing_body_keys_returns_400(self):
        response = self.client.post(
            reverse('internal:internal_catalog_items_verify'),
            data=json.dumps({}),
            content_type='application/json',
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')

    def test_facets_invalid_value_returns_400(self):
        response = self.client.get(
            reverse('internal:internal_catalog_facets') + '?facet=nonsense', **self.auth_headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_facets_get_wiring_success(self):
        response = self.client.get(reverse('internal:internal_catalog_facets'), **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'success')
        self.assertIn('categories', body)
        self.assertIn('brands', body)

    def test_embeddings_pending_rejects_post(self):
        response = self.client.post(
            reverse('internal:internal_catalog_embeddings_pending'),
            data=json.dumps({}),
            content_type='application/json',
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 405)
