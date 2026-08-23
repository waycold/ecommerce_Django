from django.test import TestCase
from apps.catalog.models import Item, Category, Brand, Supplier, Comments
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
