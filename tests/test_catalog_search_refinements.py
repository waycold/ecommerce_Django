"""
tests/test_catalog_search_refinements.py

Comprehensive test suite verifying enhanced catalog search functionality:
1. Disordered / out-of-order keywords search (e.g. "laptop strix rog asus").
2. Punctuation symbols, price tags, and extra decorators (e.g. "Gaming Laptop ROG Strix (Precio: $1499.99)").
3. Stop words handling in Spanish and English (e.g. "busco una laptop para gaming").
4. Category, brand, and description multi-attribute search matching.
5. Inactive and out-of-stock item isolation.
6. API Contract, security header (X-Internal-Secret), and parameter validation.
"""

from decimal import Decimal
import pytest
from django.conf import settings
from django.urls import reverse
from product.models import Brand, Category, Item, Supplier
from product.services import normalize_and_tokenize_query, search_catalog_service


@pytest.fixture
def catalog_dataset(db):
    """
    Sets up a structured product catalog for multi-token and multi-attribute search testing.
    """
    cat_laptops = Category.objects.create(name="Laptops")
    cat_peripherals = Category.objects.create(name="Peripherals")
    cat_processors = Category.objects.create(name="Processors")

    brand_asus = Brand.objects.create(name="Asus")
    brand_corsair = Brand.objects.create(name="Corsair")
    brand_logitech = Brand.objects.create(name="Logitech")
    brand_intel = Brand.objects.create(name="Intel")

    supplier = Supplier.objects.create(name="GlobalTech Distributor", country="USA")

    item_laptop = Item.objects.create(
        title="Gaming Laptop ROG Strix",
        description="High-end portable gaming powerhouse machine with RGB backlit keyboard",
        price=Decimal("2200.00"),
        cost=Decimal("1800.00"),
        stock=5,
        category=cat_laptops,
        brand=brand_asus,
        supplier=supplier,
        is_active=True,
    )

    item_keyboard = Item.objects.create(
        title="Mechanical Keyboard RGB",
        description="Cherry MX tactile mechanical switches for gaming and productivity typing",
        price=Decimal("150.00"),
        cost=Decimal("90.00"),
        stock=12,
        category=cat_peripherals,
        brand=brand_corsair,
        supplier=supplier,
        is_active=True,
    )

    item_mouse = Item.objects.create(
        title="Wireless Gaming Mouse Pro",
        description="Ultra-lightweight wireless gaming sensor with rechargeable battery",
        price=Decimal("80.00"),
        cost=Decimal("45.00"),
        stock=0,  # Out of stock
        category=cat_peripherals,
        brand=brand_logitech,
        supplier=supplier,
        is_active=True,
    )

    item_cpu = Item.objects.create(
        title="Core i9-13900K Processor",
        description="Flagship 24-core unlocked desktop CPU processor for workstation performance",
        price=Decimal("580.00"),
        cost=Decimal("460.00"),
        stock=8,
        category=cat_processors,
        brand=brand_intel,
        supplier=supplier,
        is_active=True,
    )

    item_inactive = Item.objects.create(
        title="Discontinued Legacy Laptop Strix",
        description="Deprecated older model laptop with strix architecture",
        price=Decimal("899.00"),
        cost=Decimal("700.00"),
        stock=10,
        category=cat_laptops,
        brand=brand_asus,
        supplier=supplier,
        is_active=False,  # Inactive item
    )

    return {
        'cat_laptops': cat_laptops,
        'cat_peripherals': cat_peripherals,
        'cat_processors': cat_processors,
        'brand_asus': brand_asus,
        'brand_corsair': brand_corsair,
        'brand_logitech': brand_logitech,
        'brand_intel': brand_intel,
        'item_laptop': item_laptop,
        'item_keyboard': item_keyboard,
        'item_mouse': item_mouse,
        'item_cpu': item_cpu,
        'item_inactive': item_inactive,
    }


def _get_items(response_data):
    """Helper to safely extract items list from response dictionary."""
    if isinstance(response_data, dict):
        return response_data.get('items', [])
    return []


# ==============================================================================
# 1. UNIT TESTS: Query Normalization & Tokenization Utility
# ==============================================================================

class TestQueryNormalizationAndTokenization:
    """
    Unit tests for normalize_and_tokenize_query service helper.
    """

    def test_normalize_empty_and_none_queries(self):
        cleaned, tokens = normalize_and_tokenize_query(None)
        assert cleaned == ""
        assert tokens == []

        cleaned, tokens = normalize_and_tokenize_query("")
        assert cleaned == ""
        assert tokens == []

        cleaned, tokens = normalize_and_tokenize_query("    ")
        assert cleaned == ""
        assert tokens == []

    def test_normalize_removes_price_prefix(self):
        cleaned, tokens = normalize_and_tokenize_query("Gaming Laptop ROG (Precio: $1499.99)")
        assert "Precio:" not in cleaned
        assert "1499.99" in cleaned
        assert "$" not in cleaned
        assert "(" not in cleaned and ")" not in cleaned
        assert "Gaming" in tokens
        assert "Laptop" in tokens
        assert "ROG" in tokens

    def test_normalize_filters_stop_words(self):
        query = "hola, busco una laptop para gaming con el mejor precio"
        cleaned, tokens = normalize_and_tokenize_query(query)
        # Stop words: hola, una, para, con, el, precio should be removed from tokens
        assert "hola" not in [t.lower() for t in tokens]
        assert "una" not in [t.lower() for t in tokens]
        assert "para" not in [t.lower() for t in tokens]
        assert "con" not in [t.lower() for t in tokens]
        assert "el" not in [t.lower() for t in tokens]
        assert "precio" not in [t.lower() for t in tokens]
        assert "laptop" in [t.lower() for t in tokens]
        assert "gaming" in [t.lower() for t in tokens]

    def test_normalize_strips_punctuation_characters(self):
        query = 'Core i9-13900K! "Processor": ($580.00)?'
        cleaned, tokens = normalize_and_tokenize_query(query)
        assert "!" not in cleaned
        assert '"' not in cleaned
        assert ":" not in cleaned
        assert "$" not in cleaned
        assert "?" not in cleaned
        assert "Core" in tokens
        assert "i9-13900K" in tokens
        assert "Processor" in tokens


# ==============================================================================
# 2. INTEGRATION TESTS: Enhanced Catalog Search Refinements
# ==============================================================================

@pytest.mark.django_db
class TestCatalogSearchRefinements:
    """
    Functional and integration tests for catalog search refinements via internal endpoint.
    """

    SEARCH_ENDPOINT = '/api/v1/internal/catalog/search/'

    def test_search_with_disordered_words(self, client, catalog_dataset):
        """
        Search with out-of-order words: "laptop strix rog asus"
        Must match "Gaming Laptop ROG Strix" (Brand: Asus).
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_ENDPOINT}?q=laptop+strix+rog+asus",
            HTTP_X_INTERNAL_SECRET=secret,
        )
        assert response.status_code == 200
        data = response.json()
        items = _get_items(data)

        assert len(items) >= 1
        top_item = items[0]
        assert top_item['id'] == catalog_dataset['item_laptop'].id
        assert top_item['title'] == "Gaming Laptop ROG Strix"
        assert top_item['brand'] == "Asus"

    def test_search_with_punctuation_and_price_decorator(self, client, catalog_dataset):
        """
        Search with punctuation and extra text: "Gaming Laptop ROG Strix (Precio: $1499.99)"
        Must strip decorators and locate the ROG Strix laptop.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_ENDPOINT}?q=Gaming+Laptop+ROG+Strix+(Precio:+%241499.99)",
            HTTP_X_INTERNAL_SECRET=secret,
        )
        assert response.status_code == 200
        data = response.json()
        items = _get_items(data)

        assert len(items) >= 1
        matched_ids = [item['id'] for item in items]
        assert catalog_dataset['item_laptop'].id in matched_ids
        assert items[0]['id'] == catalog_dataset['item_laptop'].id

    def test_search_with_stop_words_natural_language(self, client, catalog_dataset):
        """
        Search with conversational natural language and stop words: "busco una laptop para gaming"
        Must filter stop words ('una', 'para') and match the laptop.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_ENDPOINT}?q=busco+una+laptop+para+gaming",
            HTTP_X_INTERNAL_SECRET=secret,
        )
        assert response.status_code == 200
        data = response.json()
        items = _get_items(data)

        assert len(items) >= 1
        assert items[0]['id'] == catalog_dataset['item_laptop'].id
        assert "Gaming Laptop ROG Strix" in items[0]['title']

    def test_search_with_brand_and_category_combination(self, client, catalog_dataset):
        """
        Search combining brand and category names: "Intel Processors Desktop"
        Must match Core i9 processor item.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_ENDPOINT}?q=Intel+Processors+Desktop",
            HTTP_X_INTERNAL_SECRET=secret,
        )
        assert response.status_code == 200
        data = response.json()
        items = _get_items(data)

        assert len(items) >= 1
        assert items[0]['id'] == catalog_dataset['item_cpu'].id
        assert items[0]['brand'] == "Intel"
        assert items[0]['category'] == "Processors"

    def test_search_partial_keywords_case_insensitive(self, client, catalog_dataset):
        """
        Search with uppercase and lowercase variations: "KEYBOARD rgb CORSAIR"
        Must match Corsair Mechanical Keyboard.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_ENDPOINT}?q=KEYBOARD+rgb+CORSAIR",
            HTTP_X_INTERNAL_SECRET=secret,
        )
        assert response.status_code == 200
        data = response.json()
        items = _get_items(data)

        assert len(items) >= 1
        assert items[0]['id'] == catalog_dataset['item_keyboard'].id
        assert items[0]['brand'] == "Corsair"

    def test_search_excludes_inactive_items_even_with_exact_keyword_match(self, client, catalog_dataset):
        """
        Search matching inactive item keywords: "Discontinued Legacy Laptop"
        Must return empty list or only active items; inactive item must never be returned.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_ENDPOINT}?q=Discontinued+Legacy",
            HTTP_X_INTERNAL_SECRET=secret,
        )
        assert response.status_code == 200
        data = response.json()
        items = _get_items(data)

        matched_ids = [item['id'] for item in items]
        assert catalog_dataset['item_inactive'].id not in matched_ids

    def test_search_stock_availability_flag(self, client, catalog_dataset):
        """
        Verify that out-of-stock item (stock=0) has is_available=False,
        while in-stock items have is_available=True.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_ENDPOINT}?q=Wireless+Gaming+Mouse",
            HTTP_X_INTERNAL_SECRET=secret,
        )
        assert response.status_code == 200
        data = response.json()
        items = _get_items(data)

        assert len(items) >= 1
        mouse_item = next((i for i in items if i['id'] == catalog_dataset['item_mouse'].id), None)
        assert mouse_item is not None
        assert mouse_item['stock'] == 0
        assert mouse_item['is_available'] is False

    def test_search_structured_payload_fields(self, client, catalog_dataset):
        """
        Verify that all mandatory fields are present in the response schema.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_ENDPOINT}?q=ROG+Strix",
            HTTP_X_INTERNAL_SECRET=secret,
        )
        assert response.status_code == 200
        data = response.json()
        assert 'total_found' in data
        assert 'limit' in data
        assert 'items' in data

        item = data['items'][0]
        for field in ['id', 'title', 'description', 'price', 'stock', 'is_available', 'category', 'brand', 'url']:
            assert field in item, f"Missing expected field '{field}' in search item payload"

    def test_search_empty_query_returns_latest_active_items(self, client, catalog_dataset):
        """
        Query with whitespace only or empty string returns active catalog items up to limit.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_ENDPOINT}?q=+++",
            HTTP_X_INTERNAL_SECRET=secret,
        )
        assert response.status_code == 200
        data = response.json()
        items = _get_items(data)
        assert len(items) >= 4
        # Inactive item must still be excluded
        matched_ids = [item['id'] for item in items]
        assert catalog_dataset['item_inactive'].id not in matched_ids


# ==============================================================================
# 3. SECURITY & CONTRACT BOUNDARY TESTS
# ==============================================================================

@pytest.mark.django_db
class TestCatalogSearchSecurityAndBoundaries:
    """
    Security and validation tests for catalog search internal endpoint.
    """

    SEARCH_ENDPOINT = '/api/v1/internal/catalog/search/'

    def test_missing_internal_secret_returns_401(self, client):
        response = client.get(f"{self.SEARCH_ENDPOINT}?q=laptop")
        assert response.status_code == 401
        assert response.json().get('error') == 'Unauthorized'

    def test_invalid_internal_secret_returns_401(self, client):
        response = client.get(
            f"{self.SEARCH_ENDPOINT}?q=laptop",
            HTTP_X_INTERNAL_SECRET='forged-secret-header'
        )
        assert response.status_code == 401
        assert response.json().get('error') == 'Unauthorized'

    def test_disallowed_http_methods_return_405(self, client):
        secret = settings.INTERNAL_API_SECRET
        response_post = client.post(
            self.SEARCH_ENDPOINT,
            data={'q': 'laptop'},
            HTTP_X_INTERNAL_SECRET=secret,
        )
        assert response_post.status_code == 405

        response_delete = client.delete(
            self.SEARCH_ENDPOINT,
            HTTP_X_INTERNAL_SECRET=secret,
        )
        assert response_delete.status_code == 405

    def test_invalid_limit_parameter_returns_400(self, client):
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_ENDPOINT}?limit=not_an_int",
            HTTP_X_INTERNAL_SECRET=secret,
        )
        assert response.status_code == 400
        assert response.json().get('error') == 'Bad Request'

    def test_negative_limit_parameter_returns_400(self, client):
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_ENDPOINT}?limit=-10",
            HTTP_X_INTERNAL_SECRET=secret,
        )
        assert response.status_code == 400
        assert response.json().get('error') == 'Bad Request'
