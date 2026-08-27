from django.test import TestCase
from django.utils import timezone

from apps.catalog.models import (
    Item,
    Category,
    Brand,
    Supplier,
    Comments,
    ItemEmbedding,
    ProductAttribute,
    EMBEDDING_DIM,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_TEXT_VERSION,
    build_embedding_text,
)
from apps.catalog.services import search_catalog_service, normalize_and_tokenize_query


class CatalogModelTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Intel")
        self.category = Category.objects.create(name="CPU")
        self.supplier = Supplier.objects.create(name="TechCorp", country="USA")
        self.item = Item.objects.create(
            title="Core i7 13700K",
            price=450.00,
            cost=350.00,
            stock=10,
            minimum_stock=2,
            category=self.category,
            brand=self.brand,
            supplier=self.supplier
        )

    def test_item_creation(self):
        self.assertEqual(self.item.category.name, "CPU")
        self.assertEqual(self.item.brand.name, "Intel")
        self.assertEqual(self.item.supplier.name, "TechCorp")
        self.assertEqual(self.item.slug, "core-i7-13700k")

    def test_search_catalog_service(self):
        res = search_catalog_service(query="intel core i7", limit=5)
        self.assertEqual(res["total_found"], 1)
        self.assertEqual(res["items"][0]["title"], "Core i7 13700K")
        self.assertTrue(res["items"][0]["is_available"])

    def test_out_of_stock_item_flag(self):
        out_of_stock = Item.objects.create(
            title="RTX 4090",
            price=1800.00,
            cost=1400.00,
            stock=0,
            is_active=True
        )
        res = search_catalog_service(query="RTX 4090", limit=5)
        self.assertEqual(res["total_found"], 1)
        self.assertFalse(res["items"][0]["is_available"])

    def test_external_id_roundtrip_and_filter(self):
        item = Item.objects.create(
            title="Core i9 13900K",
            price=600.00,
            cost=480.00,
            external_id="B0B7XYZ123",
        )
        item.refresh_from_db()
        self.assertEqual(item.external_id, "B0B7XYZ123")
        self.assertEqual(
            Item.objects.filter(external_id="B0B7XYZ123").first().pk, item.pk
        )


class ItemEmbeddingModelTests(TestCase):
    """Phase 1 pgvector schema: basic ORM-level CRUD, unaffected by the lack
    of a real pgvector extension on SQLite (no similarity search is exercised
    here, just field storage, defaults, and relations)."""

    def setUp(self):
        self.brand = Brand.objects.create(name="Intel")
        self.category = Category.objects.create(name="CPU")
        self.item = Item.objects.create(
            title="Core i7 13700K",
            description="A high-performance desktop processor.",
            price=450.00,
            cost=350.00,
            stock=10,
            category=self.category,
            brand=self.brand,
            supplier=Supplier.objects.create(name="TechCorp", country="USA"),
        )

    def test_create_item_embedding(self):
        vector = [0.1] * EMBEDDING_DIM
        embedding = ItemEmbedding.objects.create(
            item=self.item,
            vector=vector,
            content_hash="a" * 64,
            source_updated_at=timezone.now(),
        )
        embedding.refresh_from_db()

        self.assertEqual(embedding.pk, self.item.pk)
        self.assertEqual(len(embedding.vector), EMBEDDING_DIM)
        self.assertEqual(embedding.text_version, EMBEDDING_TEXT_VERSION)
        self.assertEqual(embedding.model_name, EMBEDDING_MODEL_NAME)

    def test_item_embedding_one_to_one_relation(self):
        ItemEmbedding.objects.create(
            item=self.item,
            vector=[0.0] * EMBEDDING_DIM,
            content_hash="b" * 64,
            source_updated_at=timezone.now(),
        )

        self.assertTrue(hasattr(self.item, "embedding"))
        self.assertEqual(self.item.embedding.item_id, self.item.pk)

    def test_product_attribute_crud_and_related_name(self):
        ProductAttribute.objects.create(item=self.item, name="color", value="black")
        ProductAttribute.objects.create(item=self.item, name="socket", value="LGA1700")

        self.assertEqual(self.item.attributes.count(), 2)
        values = set(self.item.attributes.values_list("name", "value"))
        self.assertEqual(values, {("color", "black"), ("socket", "LGA1700")})

    def test_build_embedding_text_includes_expected_fields(self):
        text = build_embedding_text(self.item)

        self.assertIn("Core i7 13700K", text)
        self.assertIn("A high-performance desktop processor.", text)
        self.assertIn("CPU", text)
        self.assertIn("Intel", text)
        # Title is deliberately repeated to weigh it more heavily.
        self.assertEqual(text.count("Core i7 13700K"), 2)

    def test_build_embedding_text_excludes_supplier_and_label(self):
        self.item.label = "P"  # 'primary' - a UI badge style, not a product attribute
        self.item.save()

        text = build_embedding_text(self.item)

        self.assertNotIn("TechCorp", text)
        self.assertNotIn("primary", text)
        self.assertNotIn("USA", text)

    def test_build_embedding_text_handles_missing_optional_relations(self):
        bare_item = Item.objects.create(title="Generic Widget", price=10.00)

        text = build_embedding_text(bare_item)

        self.assertEqual(text, "Generic Widget | Generic Widget")
