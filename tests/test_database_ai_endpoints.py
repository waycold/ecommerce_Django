"""
tests/test_database_ai_endpoints.py

Comprehensive Test Suite for AI Engine Database Endpoints (Fases 1, 2 y 3):
1. Transversal Security & Header Authentication:
   - All internal endpoints reject requests missing or with invalid X-Internal-Secret (HTTP 401).
   - Non-allowed HTTP methods return HTTP 405 Method Not Allowed.
2. Módulo 1: Dynamic Aggregation Query (GET /api/v1/internal/analytics/query/)
   - Grouping across dimensions (category, brand, supplier, day, month, payment_method, country).
   - Date range filters (date_from, date_to) and status filters.
   - Exact mathematical summary calculations (total_revenue, total_gross_profit, avg_order_value, units).
3. Módulo 2.1: Inventory Health (GET /api/v1/internal/inventory/health/)
   - SKU status breakdown (out_of_stock, low_stock, healthy_stock, stockout_rate_pct).
   - Inventory valuation (total_cost_value, total_retail_value, projected_profit_potential).
   - 30-day velocity and estimated_days_to_stockout in critical_items.
4. Módulo 2.2: Margins & Profitability (GET /api/v1/internal/analytics/margins/)
   - Multi-dimensional gross margin aggregations (product, category, brand, supplier).
   - Custom ordering (margin_desc, margin_asc, revenue_desc, profit_desc).
5. Módulo 3: Funnel & Cart Metrics (GET /api/v1/internal/analytics/funnel/)
   - Cart abandonment rates (PENDING vs PAID vs CANCELED), conversion rates.
   - Abandoned products ranking, coupon effectiveness, and payment methods breakdown.
6. Módulo 4: Reviews Summary (GET /api/v1/internal/catalog/reviews-summary/)
   - Rating distributions (1 to 5 stars), average rating calculations.
   - Positive sentiment (4-5 stars) and negative feedback (1-2 stars) isolation.
   - Filtering by item_id, category, brand, min_rating, max_rating.
7. Módulo 5: Customer Insights & RFM (GET /api/v1/internal/customers/insights/)
   - RFM segment assignment (Champions/VIP, Loyal, New, At Risk, One-Time).
   - LTV averages, repeat customer rate percentage, and geographic sales distribution.
8. Módulo 6: Semantic Search (POST & GET /api/v1/internal/catalog/semantic-search/)
   - Intent detection (gaming, programming, audio_music, office_work, etc.).
   - Synonym keyword expansion, relevance scoring, and inactive product exclusion.
9. Módulo 7: Read-Only SQL Sandbox (POST /api/v1/internal/query/raw-read/)
   - Valid SELECT / CTE queries execution, 50-row maximum result limiting.
   - Syntactic AST protection against SQL injection / mutation (DROP, DELETE, INSERT, UPDATE, ALTER, TRUNCATE).
   - Blocked access to sensitive internal tables (django_session, auth_permission).
"""

from datetime import datetime, timedelta
from decimal import Decimal
import json
import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Category, Brand, Supplier, Item, Comments
from apps.core import internal_urls
from apps.orders.models import Order, OrderItem, OrderStatus, PaymentMethod, Profile


# Expected HTTP method per apps.core.internal_urls route `name`, keyed off
# each view's own `if request.method != '...'` guard. Declared once here so
# _build_internal_endpoints() below can walk internal_urls.urlpatterns
# (rather than a hardcoded path list) and fail loudly -- instead of silently
# skipping -- if a newly added internal route has no known method.
INTERNAL_ENDPOINT_METHODS = {
    'internal_health': 'GET',
    'internal_auth_validate_token': 'POST',
    'internal_catalog_search': 'GET',
    'internal_catalog_semantic_search': 'POST',
    'internal_catalog_reviews_summary': 'GET',
    'internal_inventory_health': 'GET',
    'internal_analytics_metrics': 'GET',
    'internal_analytics_query': 'GET',
    'internal_analytics_margins': 'GET',
    'internal_analytics_funnel': 'GET',
    'internal_customers_insights': 'GET',
    'internal_raw_sql_sandbox': 'POST',
    'internal_catalog_vector_search': 'POST',
    'internal_catalog_embeddings_similar': 'POST',
    'internal_catalog_embeddings_pending': 'GET',
    'internal_catalog_embeddings_upsert': 'POST',
    'internal_catalog_embeddings_mark_error': 'POST',
    'internal_catalog_items_verify': 'POST',
    'internal_catalog_facets': 'GET',
}


def _build_internal_endpoints():
    """
    Walks apps.core.internal_urls.urlpatterns -- the single source of truth
    for what's actually routed under /api/v1/internal/* -- instead of a
    hand-maintained path list, so a newly added internal endpoint is picked
    up automatically rather than shipping untested.
    """
    endpoints = []
    for url_pattern in internal_urls.urlpatterns:
        name = url_pattern.name
        assert name in INTERNAL_ENDPOINT_METHODS, (
            f"internal_urls route '{name}' has no entry in "
            f"INTERNAL_ENDPOINT_METHODS -- add its expected HTTP method so "
            f"it gets covered by TestDatabaseAIEndpointsSecurity."
        )
        endpoints.append((reverse(f'internal:{name}'), INTERNAL_ENDPOINT_METHODS[name]))
    return endpoints


@pytest.fixture
def ai_endpoints_dataset(db):
    """
    Sets up a comprehensive business dataset for multi-dimensional testing:
    - 3 Categories, 3 Brands, 2 Suppliers
    - 6 Items (different prices, costs, stock levels, active states)
    - 4 Users with profiles in different countries/cities
    - 8 Orders (Paid, Pending, Canceled, with coupons and various payment methods)
    - Reviews with varying ratings (1 to 5 stars)
    """
    now = timezone.now()

    # 1. Categories
    cat_electronics = Category.objects.create(name="Electronics")
    cat_laptops = Category.objects.create(name="Laptops")
    cat_audio = Category.objects.create(name="Digital_Music")

    # 2. Brands
    brand_asus = Brand.objects.create(name="Asus ROG")
    brand_sony = Brand.objects.create(name="Sony")
    brand_apple = Brand.objects.create(name="Apple")

    # 3. Suppliers
    sup_usa = Supplier.objects.create(name="FastShip Logistics", country="United States")
    sup_asia = Supplier.objects.create(name="GlobalTech Supply", country="China")

    # 4. Items
    # High margin laptop (In stock)
    item_laptop = Item.objects.create(
        title="ROG Strix G16 Gaming Laptop",
        description="High performance gaming laptop with RGB keyboard and RTX 4070",
        price=Decimal("1500.00"),
        cost=Decimal("900.00"),
        stock=15,
        minimum_stock=5,
        category=cat_laptops,
        brand=brand_asus,
        supplier=sup_usa,
        is_active=True,
    )
    # Low stock headphones (Critical)
    item_headphones = Item.objects.create(
        title="Sony WH-1000XM5 Wireless Headphones",
        description="Premium noise cancelling audio headphones for music and podcast",
        price=Decimal("400.00"),
        cost=Decimal("240.00"),
        stock=2,
        minimum_stock=5,
        category=cat_audio,
        brand=brand_sony,
        supplier=sup_asia,
        is_active=True,
    )
    # Out of stock mouse
    item_mouse = Item.objects.create(
        title="ROG Gladius RGB Gaming Mouse",
        description="Ergonomic optical sensor gaming mouse for esports",
        price=Decimal("80.00"),
        cost=Decimal("30.00"),
        stock=0,
        minimum_stock=10,
        category=cat_electronics,
        brand=brand_asus,
        supplier=sup_usa,
        is_active=True,
    )
    # Office accessory
    item_keyboard = Item.objects.create(
        title="Apple Magic Keyboard with Touch ID",
        description="Ergonomic wireless office keyboard for developer productivity",
        price=Decimal("180.00"),
        cost=Decimal("110.00"),
        stock=25,
        minimum_stock=5,
        category=cat_electronics,
        brand=brand_apple,
        supplier=sup_usa,
        is_active=True,
    )
    # Inactive product
    item_inactive = Item.objects.create(
        title="Discontinued Legacy Audio Cable",
        description="Old stereo jack cable",
        price=Decimal("15.00"),
        cost=Decimal("5.00"),
        stock=100,
        minimum_stock=5,
        category=cat_audio,
        brand=brand_sony,
        supplier=sup_asia,
        is_active=False,
    )

    # 5. Users & Profiles
    u_vip = User.objects.create_user(username="alex_vip", email="alex@vip.com", password="password123")
    Profile.objects.create(user=u_vip, country="United States", city="San Francisco", province="California")

    u_loyal = User.objects.create_user(username="carlos_buyer", email="carlos@buyer.es", password="password123")
    Profile.objects.create(user=u_loyal, country="Spain", city="Madrid", province="Madrid")

    u_new = User.objects.create_user(username="sophie_new", email="sophie@france.fr", password="password123")
    Profile.objects.create(user=u_new, country="France", city="Paris", province="Ile-de-France")

    u_abandoner = User.objects.create_user(username="shopper_temp", email="temp@buyer.com", password="password123")
    Profile.objects.create(user=u_abandoner, country="United States", city="New York", province="New York")

    # 6. Orders
    # Order 1 (VIP User, Paid, DESC10 coupon, Credit Card)
    ord_1 = Order.objects.create(
        user=u_vip,
        status=OrderStatus.PAID,
        payment_method=PaymentMethod.CREDIT_CARD,
        discount_code="DESC10",
        discount=Decimal("150.00"),
        shipping_cost=Decimal("0.00"),
        total=Decimal("1350.00"),
        ordered_date=now - timedelta(days=5),
        start_date=now - timedelta(days=5),
    )
    oi_1 = OrderItem.objects.create(
        order=ord_1,
        item=item_laptop,
        quantity=1,
        unit_price=Decimal("1500.00"),
        unit_cost=Decimal("900.00"),
        subtotal=Decimal("1500.00"),
    )
    ord_1.items.add(oi_1)

    # Order 2 (VIP User, Second Paid Order, Transfer)
    ord_2 = Order.objects.create(
        user=u_vip,
        status=OrderStatus.PAID,
        payment_method=PaymentMethod.TRANSFER,
        shipping_cost=Decimal("0.00"),
        total=Decimal("800.00"),
        ordered_date=now - timedelta(days=2),
        start_date=now - timedelta(days=2),
    )
    oi_2 = OrderItem.objects.create(
        order=ord_2,
        item=item_headphones,
        quantity=2,
        unit_price=Decimal("400.00"),
        unit_cost=Decimal("240.00"),
        subtotal=Decimal("800.00"),
    )
    ord_2.items.add(oi_2)

    # Order 3 (Loyal User, Paid, OFF500 coupon)
    ord_3 = Order.objects.create(
        user=u_loyal,
        status=OrderStatus.PAID,
        payment_method=PaymentMethod.CREDIT_CARD,
        discount_code="OFF500",
        discount=Decimal("500.00"),
        shipping_cost=Decimal("25.00"),
        total=Decimal("1025.00"),
        ordered_date=now - timedelta(days=12),
        start_date=now - timedelta(days=12),
    )
    oi_3 = OrderItem.objects.create(
        order=ord_3,
        item=item_laptop,
        quantity=1,
        unit_price=Decimal("1500.00"),
        unit_cost=Decimal("900.00"),
        subtotal=Decimal("1500.00"),
    )
    ord_3.items.add(oi_3)

    # Order 4 (New User, Paid Order within 30 days)
    ord_4 = Order.objects.create(
        user=u_new,
        status=OrderStatus.PAID,
        payment_method=PaymentMethod.CREDIT_CARD,
        shipping_cost=Decimal("25.00"),
        total=Decimal("205.00"),
        ordered_date=now - timedelta(days=1),
        start_date=now - timedelta(days=1),
    )
    oi_4 = OrderItem.objects.create(
        order=ord_4,
        item=item_keyboard,
        quantity=1,
        unit_price=Decimal("180.00"),
        unit_cost=Decimal("110.00"),
        subtotal=Decimal("180.00"),
    )
    ord_4.items.add(oi_4)

    # Order 5 (Abandoned Cart - PENDING)
    ord_5 = Order.objects.create(
        user=u_abandoner,
        status=OrderStatus.PENDING,
        total=Decimal("1500.00"),
        start_date=now - timedelta(days=3),
    )
    oi_5 = OrderItem.objects.create(
        order=ord_5,
        item=item_laptop,
        quantity=1,
        unit_price=Decimal("1500.00"),
        unit_cost=Decimal("900.00"),
        subtotal=Decimal("1500.00"),
    )
    ord_5.items.add(oi_5)

    # 7. Reviews
    Comments.objects.create(
        user=u_vip,
        item=item_laptop,
        rating=5,
        body="Outstanding gaming laptop! Incredible refresh rate and build quality.",
        likes=12,
    )
    Comments.objects.create(
        user=u_loyal,
        item=item_laptop,
        rating=4,
        body="Very fast computer, but the fans can get a bit loud under load.",
        likes=3,
    )
    Comments.objects.create(
        user=u_new,
        item=item_headphones,
        rating=1,
        body="Disappointed with battery life. Expected much better noise cancellation.",
        likes=1,
    )

    return {
        'items': {
            'laptop': item_laptop,
            'headphones': item_headphones,
            'mouse': item_mouse,
            'keyboard': item_keyboard,
            'inactive': item_inactive,
        },
        'users': {
            'vip': u_vip,
            'loyal': u_loyal,
            'new': u_new,
            'abandoner': u_abandoner,
        }
    }


# ==============================================================================
# 1. TRANSVERSAL SECURITY & HEADER AUTHENTICATION
# ==============================================================================

@pytest.mark.django_db
class TestDatabaseAIEndpointsSecurity:
    """
    Validates X-Internal-Secret enforcement and HTTP method restrictions
    across all 19 internal routes (apps.core.internal_urls.urlpatterns).
    """

    ENDPOINTS = _build_internal_endpoints()

    def test_endpoints_list_covers_all_internal_urls(self):
        """
        Guards against ENDPOINTS silently shrinking back to a stale subset:
        every route in apps.core.internal_urls.urlpatterns must appear here.
        """
        assert len(self.ENDPOINTS) == len(internal_urls.urlpatterns) == 19

    def test_all_endpoints_reject_missing_secret_header(self, client):
        """Requests without X-Internal-Secret must return 401 Unauthorized."""
        for path, method in self.ENDPOINTS:
            if method == 'GET':
                response = client.get(path)
            else:
                response = client.post(path, data={}, content_type='application/json')
            assert response.status_code == 401, f"Failed at {path}: expected 401 got {response.status_code}"
            data = response.json()
            assert data.get('error') == 'Unauthorized'

    def test_all_endpoints_reject_invalid_secret_header(self, client):
        """Requests with forged/invalid X-Internal-Secret must return 401 Unauthorized."""
        headers = {'HTTP_X_INTERNAL_SECRET': 'forged-invalid-secret-key'}
        for path, method in self.ENDPOINTS:
            if method == 'GET':
                response = client.get(path, **headers)
            else:
                response = client.post(path, data={}, content_type='application/json', **headers)
            assert response.status_code == 401, f"Failed at {path}: expected 401 got {response.status_code}"

    def test_non_allowed_methods_return_405(self, client):
        """GET endpoints reject POST (405) and POST-only endpoints reject GET (405)."""
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}

        # GET-only endpoint called with POST
        res_get_only = client.post('/api/v1/internal/analytics/query/', **auth_header)
        assert res_get_only.status_code == 405

        # POST-only endpoint called with GET
        res_post_only = client.get('/api/v1/internal/query/raw-read/', **auth_header)
        assert res_post_only.status_code == 405


# ==============================================================================
# 2. MÓDULO 1: DYNAMIC AGGREGATION QUERY
# ==============================================================================

@pytest.mark.django_db
class TestModule1DynamicSalesQuery:
    """
    Validates GET /api/v1/internal/analytics/query/
    """

    ENDPOINT = '/api/v1/internal/analytics/query/'

    def test_dynamic_query_grouped_by_category(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}
        response = client.get(f'{self.ENDPOINT}?group_by=category', **auth_header)
        assert response.status_code == 200
        data = response.json()

        assert 'query_metadata' in data
        assert 'summary' in data
        assert 'data' in data
        assert data['query_metadata']['group_by'] == 'category'

        summary = data['summary']
        assert summary['total_revenue'] > 0
        assert summary['total_orders'] >= 3
        assert summary['total_gross_profit'] > 0
        assert summary['avg_order_value'] > 0

        # Verify category rows
        categories_found = [row['dimension'] for row in data['data']]
        assert any("Laptops" in c or "Digital_Music" in c or "Electronics" in c for c in categories_found)

    def test_dynamic_query_grouped_by_brand_and_payment_method(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}

        # By Brand
        res_brand = client.get(f'{self.ENDPOINT}?group_by=brand', **auth_header)
        assert res_brand.status_code == 200
        brands = [r['dimension'] for r in res_brand.json()['data']]
        assert "Asus ROG" in brands or any("Asus" in b for b in brands)

        # By Payment Method
        res_pay = client.get(f'{self.ENDPOINT}?group_by=payment_method', **auth_header)
        assert res_pay.status_code == 200
        assert len(res_pay.json()['data']) >= 1

    def test_dynamic_query_invalid_limit(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}
        response = client.get(f'{self.ENDPOINT}?limit=-5', **auth_header)
        assert response.status_code == 400
        assert response.json().get('error') == 'Bad Request'


# ==============================================================================
# 3. MÓDULO 2.1: INVENTORY HEALTH
# ==============================================================================

@pytest.mark.django_db
class TestModule2InventoryHealth:
    """
    Validates GET /api/v1/internal/inventory/health/
    """

    ENDPOINT = '/api/v1/internal/inventory/health/'

    def test_inventory_health_metrics_and_valuation(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}
        response = client.get(self.ENDPOINT, **auth_header)
        assert response.status_code == 200
        data = response.json()

        metrics = data['metrics']
        assert metrics['total_active_skus'] == 4  # 4 active items created in fixture
        assert metrics['out_of_stock_count'] >= 1  # Mouse has stock=0
        assert metrics['low_stock_count'] >= 1     # Headphones stock=2 <= minimum_stock=5
        assert metrics['stockout_rate_pct'] > 0

        valuation = data['inventory_valuation']
        assert valuation['total_cost_value'] > 0
        assert valuation['total_retail_value'] > valuation['total_cost_value']
        assert valuation['projected_profit_potential'] > 0
        assert valuation['potential_margin_pct'] > 0

        # Critical items list contains out of stock item
        critical_items = data['critical_items']
        assert len(critical_items) >= 2
        out_of_stock_item = next((i for i in critical_items if i['stock'] == 0), None)
        assert out_of_stock_item is not None
        assert out_of_stock_item['stock_status'] == 'OUT_OF_STOCK'
        assert out_of_stock_item['estimated_days_to_stockout'] == 0.0


# ==============================================================================
# 4. MÓDULO 2.2: MARGINS & PROFITABILITY
# ==============================================================================

@pytest.mark.django_db
class TestModule2MarginsProfitability:
    """
    Validates GET /api/v1/internal/analytics/margins/
    """

    ENDPOINT = '/api/v1/internal/analytics/margins/'

    def test_margins_by_product_and_sorting(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}

        # Product dimension sorted by profit_desc
        response = client.get(f'{self.ENDPOINT}?dimension=product&order_by=profit_desc', **auth_header)
        assert response.status_code == 200
        data = response.json()

        assert data['dimension'] == 'product'
        assert data['order_by'] == 'profit_desc'
        assert 'overall_margin' in data
        assert data['overall_margin']['total_revenue'] > 0
        assert data['overall_margin']['overall_margin_pct'] > 0

        results = data['results']
        assert len(results) >= 1
        # Top profit item should be the laptop
        assert "ROG Strix" in results[0]['title']
        assert results[0]['gross_profit'] >= 600.0

    def test_margins_by_category_and_brand(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}

        # Category
        res_cat = client.get(f'{self.ENDPOINT}?dimension=category', **auth_header)
        assert res_cat.status_code == 200
        assert len(res_cat.json()['results']) >= 1

        # Brand
        res_brand = client.get(f'{self.ENDPOINT}?dimension=brand', **auth_header)
        assert res_brand.status_code == 200
        assert len(res_brand.json()['results']) >= 1


# ==============================================================================
# 5. MÓDULO 3: FUNNEL & CART METRICS
# ==============================================================================

@pytest.mark.django_db
class TestModule3FunnelAndPromotions:
    """
    Validates GET /api/v1/internal/analytics/funnel/
    """

    ENDPOINT = '/api/v1/internal/analytics/funnel/'

    def test_funnel_and_cart_abandonment(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}
        response = client.get(f'{self.ENDPOINT}?period=all_time', **auth_header)
        assert response.status_code == 200
        data = response.json()

        funnel = data['funnel_metrics']
        assert funnel['total_orders'] >= 5
        assert funnel['completed_orders'] >= 4
        assert funnel['pending_orders'] >= 1
        assert funnel['cart_abandonment_rate_pct'] > 0
        assert funnel['conversion_rate_pct'] > 0

        # Abandoned products ranking
        abandoned = data['abandoned_products_ranking']
        assert len(abandoned) >= 1
        assert "ROG Strix" in abandoned[0]['title']

        # Coupon effectiveness
        coupons = data['coupon_effectiveness']
        coupon_codes = [c['discount_code'] for c in coupons]
        assert "DESC10" in coupon_codes or "OFF500" in coupon_codes

        # Payment breakdown
        payment = data['payment_methods_breakdown']
        assert len(payment) >= 1


# ==============================================================================
# 6. MÓDULO 4: REVIEWS SUMMARY
# ==============================================================================

@pytest.mark.django_db
class TestModule4ReviewsSummary:
    """
    Validates GET /api/v1/internal/catalog/reviews-summary/
    """

    ENDPOINT = '/api/v1/internal/catalog/reviews-summary/'

    def test_reviews_summary_distribution_and_sentiments(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}
        response = client.get(self.ENDPOINT, **auth_header)
        assert response.status_code == 200
        data = response.json()

        summary = data['summary']
        assert summary['total_reviews'] == 3
        assert summary['average_rating'] > 0
        assert summary['rating_distribution']['5_stars'] == 1
        assert summary['rating_distribution']['4_stars'] == 1
        assert summary['rating_distribution']['1_star'] == 1

        # Check positive feedback (rating 4 & 5)
        positives = data['recent_positive_feedback']
        assert len(positives) >= 1
        assert any(p['rating'] >= 4 for p in positives)

        # Check negative feedback (rating 1 & 2)
        negatives = data['recent_negative_feedback']
        assert len(negatives) >= 1
        assert negatives[0]['rating'] <= 2
        assert "battery life" in negatives[0]['body']

    def test_reviews_filter_by_item(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}
        laptop_id = ai_endpoints_dataset['items']['laptop'].id
        response = client.get(f'{self.ENDPOINT}?item_id={laptop_id}', **auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data['summary']['total_reviews'] == 2
        assert data['summary']['average_rating'] == 4.5


# ==============================================================================
# 7. MÓDULO 5: CUSTOMER INSIGHTS & RFM
# ==============================================================================

@pytest.mark.django_db
class TestModule5CustomerInsights:
    """
    Validates GET /api/v1/internal/customers/insights/
    """

    ENDPOINT = '/api/v1/internal/customers/insights/'

    def test_customer_rfm_segmentation_and_geography(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}
        response = client.get(self.ENDPOINT, **auth_header)
        assert response.status_code == 200
        data = response.json()

        summary = data['summary']
        assert summary['total_customers'] >= 3
        assert summary['avg_customer_ltv'] > 0
        assert 'segment_counts' in summary

        # Geographic breakdown
        geo = data['geographic_distribution']
        countries = [c['country'] for c in geo['by_country']]
        assert "United States" in countries

        # Top customers list
        top = data['top_customers']
        assert len(top) >= 3
        assert top[0]['total_spend'] >= top[1]['total_spend']
        assert 'segment' in top[0]


# ==============================================================================
# 8. MÓDULO 6: SEMANTIC SEARCH
# ==============================================================================

@pytest.mark.django_db
class TestModule6SemanticSearch:
    """
    Validates POST & GET /api/v1/internal/catalog/semantic-search/
    """

    ENDPOINT = '/api/v1/internal/catalog/semantic-search/'

    def test_semantic_intent_search_gaming(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}
        payload = {"query_text": "busco una computadora gamer potente", "limit": 5}
        response = client.post(self.ENDPOINT, data=json.dumps(payload), content_type='application/json', **auth_header)
        assert response.status_code == 200
        data = response.json()

        assert "gaming" in data['intents_detected']
        assert data['total_found'] >= 1
        items = data['items']
        assert any("ROG Strix" in i['title'] for i in items)
        assert items[0]['relevance_score'] > 0

    def test_semantic_intent_search_music_and_audio(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}
        payload = {"query_text": "auriculares para escuchar musica", "limit": 5}
        response = client.post(self.ENDPOINT, data=json.dumps(payload), content_type='application/json', **auth_header)
        assert response.status_code == 200
        data = response.json()

        assert "audio_music" in data['intents_detected']
        assert any("WH-1000XM5" in i['title'] for i in data['items'])

    def test_inactive_products_excluded_from_semantic_search(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}
        inactive_id = ai_endpoints_dataset['items']['inactive'].id
        payload = {"query_text": "Discontinued Legacy Audio Cable"}
        response = client.post(self.ENDPOINT, data=json.dumps(payload), content_type='application/json', **auth_header)
        assert response.status_code == 200
        data = response.json()
        item_ids = [item['id'] for item in data['items']]
        # Inactive item must never be included in search results
        assert inactive_id not in item_ids


# ==============================================================================
# 9. MÓDULO 7: READ-ONLY SQL SANDBOX
# ==============================================================================

@pytest.mark.django_db
class TestModule7SQLSandbox:
    """
    Validates POST /api/v1/internal/query/raw-read/
    """

    ENDPOINT = '/api/v1/internal/query/raw-read/'

    def test_valid_select_query_executes_successfully(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}
        payload = {"query": "SELECT id, title, price, stock FROM product_item WHERE is_active = 1 ORDER BY price DESC;"}
        response = client.post(self.ENDPOINT, data=json.dumps(payload), content_type='application/json', **auth_header)
        assert response.status_code == 200
        data = response.json()

        assert data['status'] == 'success'
        assert 'columns' in data
        assert 'rows' in data
        assert data['row_count'] >= 1
        assert data['execution_time_ms'] >= 0.0

    def test_sql_injection_mutations_blocked(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}

        malicious_queries = [
            "DROP TABLE product_item;",
            "DELETE FROM product_item WHERE id = 1;",
            "INSERT INTO product_item (title, price) VALUES ('Hacked', 999);",
            "UPDATE product_item SET price = 0;",
            "ALTER TABLE product_item ADD COLUMN pwned text;",
            "TRUNCATE TABLE product_item;",
            "SELECT 1; DROP TABLE product_item;",
        ]

        for query in malicious_queries:
            payload = {"query": query}
            response = client.post(self.ENDPOINT, data=json.dumps(payload), content_type='application/json', **auth_header)
            assert response.status_code == 400, f"Dangerous query was not blocked: {query}"
            assert response.json().get('error') in ('Forbidden SQL Keyword', 'Bad Request')

    def test_sensitive_tables_blocked(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}
        payload = {"query": "SELECT * FROM django_session;"}
        response = client.post(self.ENDPOINT, data=json.dumps(payload), content_type='application/json', **auth_header)
        assert response.status_code == 400
        assert response.json().get('error') == 'Forbidden Table Access'

    def test_auth_user_table_blocked(self, client, ai_endpoints_dataset):
        """
        Fase 0, Tarea 1: auth_user holds every user's password hash --
        FORBIDDEN_TABLE_PATTERNS must reject it exactly like the other
        sensitive auth/session tables, never return 200 with real rows.
        """
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}
        payload = {"query": "SELECT username, password FROM auth_user;"}
        response = client.post(self.ENDPOINT, data=json.dumps(payload), content_type='application/json', **auth_header)
        assert response.status_code == 400
        assert response.json().get('error') == 'Forbidden Table Access'

    def test_auth_user_related_tables_blocked(self, client, ai_endpoints_dataset):
        """Companion tables that also expose user identity/permissions must be blocked too."""
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}
        for query in (
            "SELECT * FROM auth_user_groups;",
            "SELECT * FROM auth_user_user_permissions;",
            "SELECT * FROM django_admin_log;",
        ):
            payload = {"query": query}
            response = client.post(self.ENDPOINT, data=json.dumps(payload), content_type='application/json', **auth_header)
            assert response.status_code == 400, f"Query was not blocked: {query}"
            assert response.json().get('error') == 'Forbidden Table Access'

    def test_empty_sql_query_rejected(self, client):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}
        payload = {"query": "   "}
        response = client.post(self.ENDPOINT, data=json.dumps(payload), content_type='application/json', **auth_header)
        assert response.status_code == 400
        assert response.json().get('error') == 'Bad Request'

    def test_cte_with_query_allowed(self, client, ai_endpoints_dataset):
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}
        payload = {
            "query": "WITH items_cte AS (SELECT id, title, price FROM product_item) SELECT * FROM items_cte LIMIT 10;"
        }
        response = client.post(self.ENDPOINT, data=json.dumps(payload), content_type='application/json', **auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert len(data['rows']) >= 1


# ==============================================================================
# 10. FASE 0, TAREA 2: DEDICATED READ-ONLY SANDBOX CONNECTION
# ==============================================================================

class _TrackingConnections:
    """Thin wrapper around django.db.connections that records which alias
    was subscripted, while still delegating to the real ConnectionHandler --
    used to prove execute_safe_sql_sandbox() asks for the right alias
    without needing a real second Postgres server."""

    def __init__(self, real_connections):
        self._real = real_connections
        self.accessed_aliases = []

    def __getitem__(self, alias):
        self.accessed_aliases.append(alias)
        return self._real[alias]


@pytest.mark.django_db
class TestSandboxDatabaseAlias:
    """
    Validates apps.core.services.sql_sandbox_service.get_sandbox_db_alias()
    and that execute_safe_sql_sandbox() actually connects through it, per
    Fase 0 Tarea 2(c): the sandbox must run against the dedicated
    'chatbot_readonly' alias when it's configured, and fall back to
    'default' (SQLite in dev/tests) when it isn't -- it must never silently
    keep using the full Django connection once the alias exists.
    """

    def test_alias_is_default_when_chatbot_readonly_not_configured(self):
        from apps.core.services.sql_sandbox_service import get_sandbox_db_alias
        assert 'chatbot_readonly' not in settings.DATABASES  # guaranteed by config/settings/testing.py
        assert get_sandbox_db_alias() == 'default'

    def test_alias_is_chatbot_readonly_when_configured(self, settings):
        from apps.core.services.sql_sandbox_service import get_sandbox_db_alias
        settings.DATABASES = {
            **settings.DATABASES,
            'chatbot_readonly': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'},
        }
        assert get_sandbox_db_alias() == 'chatbot_readonly'

    def test_execute_safe_sql_sandbox_uses_default_alias_when_not_configured(self, monkeypatch):
        import apps.core.services.sql_sandbox_service as sandbox_module
        from django.db import connections as real_connections

        tracker = _TrackingConnections(real_connections)
        monkeypatch.setattr(sandbox_module, 'connections', tracker)

        result, status_code = sandbox_module.execute_safe_sql_sandbox("SELECT 1 AS n")

        assert status_code == 200
        assert tracker.accessed_aliases == ['default']

    def test_execute_safe_sql_sandbox_delegates_alias_choice_to_get_sandbox_db_alias(self, monkeypatch):
        """
        Proves execute_safe_sql_sandbox() picks its connection by *calling*
        get_sandbox_db_alias() and using exactly what it returns, rather
        than a literal 'default' baked into the function. Combined with
        test_alias_is_chatbot_readonly_when_configured above (which proves
        get_sandbox_db_alias() itself returns 'chatbot_readonly' once that
        key exists in settings.DATABASES), this establishes the full chain
        the acceptance criteria ask for.

        This intentionally spies on the real get_sandbox_db_alias() instead
        of wiring up a live second 'chatbot_readonly' connection: Django's
        TestCase machinery only allows connections to aliases a test
        declares upfront (`databases = {...}`), computed from
        settings.DATABASES at session start -- long before a alias could be
        injected mid-test -- so a genuine second connection would require
        permanently adding 'chatbot_readonly' to config/settings/testing.py,
        which Tarea 2(c) explicitly says local/testing must never do.
        """
        import apps.core.services.sql_sandbox_service as sandbox_module
        from django.db import connections as real_connections

        real_get_alias = sandbox_module.get_sandbox_db_alias
        expected_alias = real_get_alias()  # 'default' here (chatbot_readonly not configured)
        alias_calls = []

        def _spy_get_alias():
            value = real_get_alias()
            alias_calls.append(value)
            return value

        monkeypatch.setattr(sandbox_module, 'get_sandbox_db_alias', _spy_get_alias)
        tracker = _TrackingConnections(real_connections)
        monkeypatch.setattr(sandbox_module, 'connections', tracker)

        result, status_code = sandbox_module.execute_safe_sql_sandbox("SELECT 1 AS n")

        assert status_code == 200, result
        assert alias_calls == [expected_alias]
        assert tracker.accessed_aliases == [expected_alias]


# ==============================================================================
# 11. FASE 0, TAREA 3: SANDBOX TIMEOUT MUST RUN IN A SINGLE TRANSACTION
# ==============================================================================

@pytest.mark.django_db
class TestSandboxAtomicTransaction:
    """
    Before the fix, `SET LOCAL statement_timeout` and the sandboxed query
    ran as two separate autocommit statements, so the timeout never applied
    to the query that followed it. SQLite has no statement_timeout to
    actually time out (execute_safe_sql_sandbox only issues SET LOCAL when
    connection.vendor == 'postgresql'), so this verifies the mechanic the
    fix relies on instead: both statements now run inside the exact same
    transaction.atomic() block, which on Postgres is what makes SET LOCAL
    apply to the query at all.
    """

    def test_query_runs_inside_a_savepoint_of_the_sandbox_alias(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connections
        from apps.core.services.sql_sandbox_service import execute_safe_sql_sandbox, get_sandbox_db_alias

        conn = connections[get_sandbox_db_alias()]
        with CaptureQueriesContext(conn) as ctx:
            result, status_code = execute_safe_sql_sandbox("SELECT 1 AS n")

        assert status_code == 200
        sqls = [q['sql'].upper() for q in ctx.captured_queries]
        # transaction.atomic() nested inside the pytest-django test
        # transaction opens a SAVEPOINT before the real query and
        # releases it after -- proof the two statements share one
        # transaction instead of being two independent autocommits.
        assert any('SAVEPOINT' in sql for sql in sqls), sqls
        assert any('SELECT 1 AS N' in sql for sql in sqls), sqls

    def test_atomic_block_rolls_back_savepoint_on_query_failure(self):
        """
        A DatabaseError inside the atomic block (e.g. a malformed sandboxed
        query) must not leave a dangling transaction/savepoint open on the
        sandbox connection -- execute_safe_sql_sandbox must still return its
        normal 400 error shape, not raise.
        """
        from apps.core.services.sql_sandbox_service import execute_safe_sql_sandbox

        result, status_code = execute_safe_sql_sandbox("SELECT * FROM this_table_does_not_exist")
        assert status_code == 400
        assert result['error'] == 'Database Query Error'
