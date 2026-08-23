import pytest
from decimal import Decimal
from django.conf import settings
from apps.catalog.models import Brand, Category, Item, Supplier


@pytest.fixture
def catalog_setup(db):
    """
    Fixture creating a structured catalog dataset for testing search, filtering, and availability.
    """
    cat_laptops = Category.objects.create(name="Laptops")
    cat_peripherals = Category.objects.create(name="Peripherals")
    cat_cpus = Category.objects.create(name="Processors")

    brand_asus = Brand.objects.create(name="Asus")
    brand_corsair = Brand.objects.create(name="Corsair")
    brand_logitech = Brand.objects.create(name="Logitech")
    brand_intel = Brand.objects.create(name="Intel")

    supplier = Supplier.objects.create(name="GlobalTech", country="USA")

    item_laptop = Item.objects.create(
        title="Gaming Laptop ROG Strix",
        description="High-end portable powerhouse machine",
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
        description="Cherry MX tactile switches for typing",
        price=Decimal("150.00"),
        cost=Decimal("90.00"),
        stock=12,
        category=cat_peripherals,
        brand=brand_corsair,
        supplier=supplier,
        is_active=True,
    )

    item_mouse = Item.objects.create(
        title="Wireless Gaming Mouse",
        description="Ultra-lightweight gaming sensor",
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
        description="Flagship 24-core desktop processor",
        price=Decimal("580.00"),
        cost=Decimal("460.00"),
        stock=8,
        category=cat_cpus,
        brand=brand_intel,
        supplier=supplier,
        is_active=True,
    )

    item_inactive = Item.objects.create(
        title="Discontinued Laptop Ultra",
        description="Deprecated legacy laptop",
        price=Decimal("999.00"),
        cost=Decimal("800.00"),
        stock=10,
        category=cat_laptops,
        brand=brand_asus,
        supplier=supplier,
        is_active=False,  # Inactive item
    )

    return {
        'cat_laptops': cat_laptops,
        'cat_peripherals': cat_peripherals,
        'cat_cpus': cat_cpus,
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


def _extract_items(data):
    """
    Helper to extract items list from response dictionary or list.
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if 'items' in data:
            return data['items']
        if 'results' in data:
            return data['results']
    return []


@pytest.mark.django_db
class TestCatalogSearchContract:
    """
    Test suite for Contract 1: Catalog Search API (GET /api/v1/internal/catalog/search/).
    """

    SEARCH_URL = '/api/v1/internal/catalog/search/'

    def test_catalog_search_unauthorized_missing_secret(self, client):
        """
        Requesting catalog search without X-Internal-Secret returns 401 Unauthorized.
        """
        response = client.get(self.SEARCH_URL)
        assert response.status_code == 401
        data = response.json()
        assert data.get('error') == 'Unauthorized'

    def test_catalog_search_unauthorized_wrong_secret(self, client):
        """
        Requesting catalog search with an invalid secret returns 401 Unauthorized.
        """
        response = client.get(
            self.SEARCH_URL,
            HTTP_X_INTERNAL_SECRET='wrong-secret-token'
        )
        assert response.status_code == 401
        data = response.json()
        assert data.get('error') == 'Unauthorized'

    def test_catalog_search_disallowed_methods(self, client):
        """
        POST, PUT, DELETE methods on /api/v1/internal/catalog/search/ return 405 Method Not Allowed.
        """
        secret = settings.INTERNAL_API_SECRET
        response_post = client.post(
            self.SEARCH_URL,
            data={'q': 'Laptop'},
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response_post.status_code == 405

        response_put = client.put(
            self.SEARCH_URL,
            data={'q': 'Laptop'},
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response_put.status_code == 405

        response_delete = client.delete(
            self.SEARCH_URL,
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response_delete.status_code == 405

    def test_catalog_search_by_text_title(self, client, catalog_setup):
        """
        Search by query string matching item title.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_URL}?q=Strix",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        items = _extract_items(data)
        assert len(items) == 1
        assert items[0]['id'] == catalog_setup['item_laptop'].id
        assert 'Gaming Laptop ROG Strix' in items[0]['title']

    def test_catalog_search_by_text_brand(self, client, catalog_setup):
        """
        Search by query string matching brand name.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_URL}?q=Corsair",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        items = _extract_items(data)
        assert len(items) == 1
        assert items[0]['id'] == catalog_setup['item_keyboard'].id

    def test_catalog_search_by_text_category(self, client, catalog_setup):
        """
        Search by query string matching category name.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_URL}?q=Processors",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        items = _extract_items(data)
        assert len(items) == 1
        assert items[0]['id'] == catalog_setup['item_cpu'].id

    def test_catalog_search_by_text_description(self, client, catalog_setup):
        """
        Search by query string matching description content.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_URL}?q=powerhouse",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        items = _extract_items(data)
        assert len(items) == 1
        assert items[0]['id'] == catalog_setup['item_laptop'].id

    def test_catalog_search_by_text_no_matches(self, client, catalog_setup):
        """
        Search with query string that has no match returns empty items list.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_URL}?q=nonexistentitem12345",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        items = _extract_items(data)
        assert len(items) == 0
        assert data.get('total_found', 0) == 0

    def test_catalog_search_filter_by_category_id(self, client, catalog_setup):
        """
        Filter products by category ID.
        """
        secret = settings.INTERNAL_API_SECRET
        cat_id = catalog_setup['cat_peripherals'].id
        response = client.get(
            f"{self.SEARCH_URL}?category={cat_id}",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        items = _extract_items(data)
        assert len(items) == 2
        item_ids = {r['id'] for r in items}
        assert catalog_setup['item_keyboard'].id in item_ids
        assert catalog_setup['item_mouse'].id in item_ids

    def test_catalog_search_filter_by_category_name(self, client, catalog_setup):
        """
        Filter products by category name (case-insensitive).
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_URL}?category=peripherals",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        items = _extract_items(data)
        assert len(items) == 2
        item_ids = {r['id'] for r in items}
        assert catalog_setup['item_keyboard'].id in item_ids
        assert catalog_setup['item_mouse'].id in item_ids

    def test_catalog_search_filter_by_nonexistent_category(self, client, catalog_setup):
        """
        Filter by non-existent category returns empty results.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_URL}?category=NonExistentCategory",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        items = _extract_items(data)
        assert len(items) == 0

    def test_catalog_search_limit_parameter(self, client, catalog_setup):
        """
        Limit parameter returns only the specified number of items.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_URL}?limit=2",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        items = _extract_items(data)
        assert len(items) == 2
        assert data.get('limit') == 2

    def test_catalog_search_limit_invalid_string(self, client, catalog_setup):
        """
        Invalid string value for limit returns 400 Bad Request.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_URL}?limit=invalid_number",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 400
        data = response.json()
        assert data.get('error') == 'Bad Request'

    def test_catalog_search_limit_invalid_zero_and_negative(self, client, catalog_setup):
        """
        Zero or negative limit returns 400 Bad Request.
        """
        secret = settings.INTERNAL_API_SECRET
        response_zero = client.get(
            f"{self.SEARCH_URL}?limit=0",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response_zero.status_code == 400

        response_negative = client.get(
            f"{self.SEARCH_URL}?limit=-5",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response_negative.status_code == 400

    def test_catalog_search_limit_max_50(self, client, db):
        """
        Limit is capped at maximum 50 results even if a larger number is requested.
        """
        brand = Brand.objects.create(name="BulkBrand")
        category = Category.objects.create(name="BulkCat")
        items = [
            Item(
                title=f"Bulk Item {i}",
                slug=f"bulk-item-{i}",
                price=Decimal("10.00"),
                cost=Decimal("5.00"),
                stock=5,
                category=category,
                brand=brand,
                is_active=True,
            )
            for i in range(60)
        ]
        Item.objects.bulk_create(items)

        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_URL}?limit=100",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        items = _extract_items(data)
        assert len(items) <= 50
        assert data.get('limit') == 50

    def test_catalog_search_availability_and_absolute_urls(self, client, catalog_setup):
        """
        Verify that is_available reflects stock > 0, and url returns valid absolute URLs.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            self.SEARCH_URL,
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        items = _extract_items(data)
        assert len(items) >= 4

        results_by_id = {r['id']: r for r in items}

        # Item with stock=5 -> is_available=True
        laptop_data = results_by_id.get(catalog_setup['item_laptop'].id)
        assert laptop_data is not None
        assert laptop_data['is_available'] is True
        assert laptop_data['stock'] == 5
        assert laptop_data['url'].startswith('http://') or laptop_data['url'].startswith('https://')

        # Item with stock=0 -> is_available=False
        mouse_data = results_by_id.get(catalog_setup['item_mouse'].id)
        assert mouse_data is not None
        assert mouse_data['is_available'] is False
        assert mouse_data['stock'] == 0
        assert mouse_data['url'].startswith('http://') or mouse_data['url'].startswith('https://')

    def test_catalog_search_excludes_inactive_items(self, client, catalog_setup):
        """
        Inactive items (is_active=False) must never be returned in search results.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_URL}?q=Discontinued",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        items = _extract_items(data)
        assert len(items) == 0

        # Also verify inactive item is not present in general catalog search
        response_all = client.get(
            f"{self.SEARCH_URL}?limit=50",
            HTTP_X_INTERNAL_SECRET=secret
        )
        data_all = response_all.json()
        items_all = _extract_items(data_all)
        all_ids = {r['id'] for r in items_all}
        assert catalog_setup['item_inactive'].id not in all_ids

    def test_catalog_search_with_price_prefix_and_punctuation(self, client, catalog_setup):
        """
        Queries containing price prefixes and punctuation (e.g. 'Gaming Laptop ROG Strix (Precio: $1499.99)')
        are cleaned and match the expected item.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_URL}?q=Gaming+Laptop+ROG+Strix+(Precio:+$1499.99)",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        items = _extract_items(data)
        assert len(items) >= 1
        assert items[0]['id'] == catalog_setup['item_laptop'].id

    def test_catalog_search_multi_token_across_fields(self, client, catalog_setup):
        """
        Queries with multiple tokens matching across title and brand (e.g. 'laptop rog asus')
        successfully match the item and rank it at the top.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_URL}?q=laptop+rog+asus",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        items = _extract_items(data)
        assert len(items) >= 1
        assert items[0]['id'] == catalog_setup['item_laptop'].id

    def test_catalog_search_stop_words_filtering(self, client, catalog_setup):
        """
        Queries containing Spanish or English stop words are filtered to significant keywords.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_URL}?q=hola+me+interesa+el+producto+Mechanical+Keyboard+RGB",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        items = _extract_items(data)
        assert len(items) >= 1
        assert items[0]['id'] == catalog_setup['item_keyboard'].id

    def test_catalog_search_exact_match_priority(self, client, catalog_setup):
        """
        Exact title matches are ranked higher than partial description/token matches.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(
            f"{self.SEARCH_URL}?q=Mechanical+Keyboard+RGB",
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        items = _extract_items(data)
        assert len(items) >= 1
        assert items[0]['id'] == catalog_setup['item_keyboard'].id

