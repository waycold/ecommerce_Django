from django.test import TestCase

from apps.catalog.attribute_mapping import map_details_to_attributes
from apps.catalog.models import Brand, Category, Item, ProductAttribute, Supplier


class MapDetailsToAttributesTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Generic")
        self.category = Category.objects.create(name="Electronics")
        self.supplier = Supplier.objects.create(name="Acme", country="USA")
        self.item = Item.objects.create(
            title="Test Item",
            price=10.00,
            cost=5.00,
            stock=1,
            minimum_stock=1,
            category=self.category,
            brand=self.brand,
            supplier=self.supplier,
        )

    def test_normal_details_dict_with_known_keys(self):
        details = {
            "Color": "Black",
            "Material": "Aluminum",
            "Item model number": "XYZ123",  # unknown key, should be dropped
        }
        attrs = map_details_to_attributes(self.item, details)
        by_name = {a.name: a.value for a in attrs}

        self.assertEqual(by_name.get("color"), "Black")
        self.assertEqual(by_name.get("material"), "Aluminum")
        self.assertNotIn("Item model number", by_name)
        self.assertEqual(len(attrs), 2)
        for a in attrs:
            self.assertIsInstance(a, ProductAttribute)
            self.assertEqual(a.item, self.item)

    def test_empty_dict_returns_empty_list(self):
        self.assertEqual(map_details_to_attributes(self.item, {}), [])

    def test_none_returns_empty_list(self):
        self.assertEqual(map_details_to_attributes(self.item, None), [])

    def test_non_dict_returns_empty_list(self):
        self.assertEqual(map_details_to_attributes(self.item, "not a dict"), [])
        self.assertEqual(map_details_to_attributes(self.item, ["also", "not", "a", "dict"]), [])

    def test_only_unknown_keys_maps_to_nothing(self):
        details = {
            "Date First Available": "January 1, 2020",
            "Item Weight": "1 pound",
            "Best Sellers Rank": {"Electronics": 1234},
        }
        self.assertEqual(map_details_to_attributes(self.item, details), [])

    def test_non_string_value_is_coerced(self):
        details = {"Size": 42}
        attrs = map_details_to_attributes(self.item, details)
        self.assertEqual(len(attrs), 1)
        self.assertEqual(attrs[0].name, "size")
        self.assertEqual(attrs[0].value, "42")

    def test_nested_dict_value_for_known_key_is_coerced_not_crashed(self):
        details = {"Brand": {"unexpected": "shape"}}
        attrs = map_details_to_attributes(self.item, details)
        self.assertEqual(len(attrs), 1)
        self.assertEqual(attrs[0].name, "brand")
        # str() of a dict, just must not crash and must fit max_length=100
        self.assertLessEqual(len(attrs[0].value), 100)

    def test_value_longer_than_100_chars_is_truncated(self):
        long_value = "X" * 250
        details = {"Color": long_value}
        attrs = map_details_to_attributes(self.item, details)
        self.assertEqual(len(attrs), 1)
        self.assertEqual(attrs[0].value, long_value[:100])
        self.assertEqual(len(attrs[0].value), 100)

    def test_empty_or_whitespace_value_is_skipped(self):
        details = {"Color": "   ", "Material": ""}
        self.assertEqual(map_details_to_attributes(self.item, details), [])

    def test_case_insensitive_key_matching(self):
        details = {"color": "Red", "MATERIAL": "Steel", "BrAnD": "Acme"}
        attrs = map_details_to_attributes(self.item, details)
        by_name = {a.name: a.value for a in attrs}
        self.assertEqual(by_name.get("color"), "Red")
        self.assertEqual(by_name.get("material"), "Steel")
        self.assertEqual(by_name.get("brand"), "Acme")

    def test_department_maps_to_gender(self):
        details = {"Department": "womens"}
        attrs = map_details_to_attributes(self.item, details)
        self.assertEqual(len(attrs), 1)
        self.assertEqual(attrs[0].name, "gender")
        self.assertEqual(attrs[0].value, "womens")

    def test_falsy_but_non_empty_value_is_kept(self):
        details = {"Size": 0}
        attrs = map_details_to_attributes(self.item, details)
        self.assertEqual(len(attrs), 1)
        self.assertEqual(attrs[0].name, "size")
        self.assertEqual(attrs[0].value, "0")

    def test_value_with_surrounding_whitespace_is_stripped(self):
        details = {"Color": "  Red  "}
        attrs = map_details_to_attributes(self.item, details)
        self.assertEqual(len(attrs), 1)
        self.assertEqual(attrs[0].value, "Red")

    def test_first_empty_synonym_then_valid_synonym_uses_the_valid_one(self):
        details = {"Brand": "", "Brand Name": "Acme"}
        attrs = map_details_to_attributes(self.item, details)
        self.assertEqual(len(attrs), 1)
        self.assertEqual(attrs[0].name, "brand")
        self.assertEqual(attrs[0].value, "Acme")

    def test_duplicate_attribute_keys_keep_first_occurrence(self):
        # dict iteration order is insertion order in Python 3.7+
        details = {"Brand": "First", "Brand Name": "Second"}
        attrs = map_details_to_attributes(self.item, details)
        self.assertEqual(len(attrs), 1)
        self.assertEqual(attrs[0].value, "First")
