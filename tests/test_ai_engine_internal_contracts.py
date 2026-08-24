"""
tests/test_ai_engine_internal_contracts.py

Comprehensive test suite validating all 7 new internal AI engine database endpoints,
security guardrails, aggregations, and edge cases across Fases 1, 2, and 3.
"""

import pytest
from decimal import Decimal
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User

from apps.catalog.models import Category, Brand, Supplier, Item, Comments
from apps.orders.models import Order, OrderItem, Profile, OrderStatus, PaymentMethod


@pytest.fixture
def ai_engine_dataset(db):
    """
    Creates a rich test database fixture for AI engine endpoints.
    """
    # Categories & Brands
    cat_tech = Category.objects.create(name="Electronics")
    cat_office = Category.objects.create(name="Office_Products")
    
    brand_asus = Brand.objects.create(name="Asus")
    brand_logi = Brand.objects.create(name="Logitech")
    
    supplier = Supplier.objects.create(name="GlobalSupply", country="USA")

    # Items
    laptop = Item.objects.create(
        title="Gaming Laptop ROG Strix RTX",
        description="High-end portable gamer powerhouse with mechanical keyboard",
        price=Decimal("2000.00"),
        cost=Decimal("1200.00"),
        stock=5,
        minimum_stock=10,
        category=cat_tech,
        brand=brand_asus,
        supplier=supplier,
        is_active=True,
    )

    mouse = Item.objects.create(
        title="Ergonomic Wireless Office Mouse",
        description="Comfortable productivity mouse for desk work and programming",
        price=Decimal("80.00"),
        cost=Decimal("40.00"),
        stock=0,  # Out of stock
        minimum_stock=15,
        category=cat_office,
        brand=brand_logi,
        supplier=supplier,
        is_active=True,
    )

    keyboard = Item.objects.create(
        title="Mechanical Keyboard RGB Pro",
        description="Tactile switches for typing and gaming",
        price=Decimal("150.00"),
        cost=Decimal("90.00"),
        stock=20,
        minimum_stock=5,
        category=cat_tech,
        brand=brand_logi,
        supplier=supplier,
        is_active=True,
    )

    # Users & Profiles
    user1 = User.objects.create_user(username="vip_user", email="vip@example.com", password="pass123")
    Profile.objects.create(user=user1, country="United States", city="New York")

    user2 = User.objects.create_user(username="intl_user", email="intl@example.com", password="pass123")
    Profile.objects.create(user=user2, country="Germany", city="Berlin")

    user3 = User.objects.create_user(username="new_user", email="new@example.com", password="pass123")
    Profile.objects.create(user=user3, country="United States", city="Austin")

    now = timezone.now()

    # Completed Orders
    order1 = Order.objects.create(
        user=user1,
        status=OrderStatus.PAID,
        payment_method=PaymentMethod.CREDIT_CARD,
        discount_code="DESC10",
        discount=Decimal("200.00"),
        shipping_cost=Decimal("500.00"),
        total=Decimal("2300.00"),
        ordered_date=now - timedelta(days=5),
    )
    OrderItem.objects.create(order=order1, item=laptop, quantity=1, unit_price=Decimal("2000.00"), unit_cost=Decimal("1200.00"), subtotal=Decimal("2000.00"))

    order2 = Order.objects.create(
        user=user1,
        status=OrderStatus.SHIPPED,
        payment_method=PaymentMethod.DEBIT_CARD,
        shipping_cost=Decimal("500.00"),
        total=Decimal("650.00"),
        ordered_date=now - timedelta(days=15),
    )
    OrderItem.objects.create(order=order2, item=keyboard, quantity=1, unit_price=Decimal("150.00"), unit_cost=Decimal("90.00"), subtotal=Decimal("150.00"))

    order3 = Order.objects.create(
        user=user2,
        status=OrderStatus.DELIVERED,
        payment_method=PaymentMethod.TRANSFER,
        shipping_cost=Decimal("2500.00"),
        total=Decimal("2650.00"),
        ordered_date=now - timedelta(days=25),
    )
    OrderItem.objects.create(order=order3, item=keyboard, quantity=1, unit_price=Decimal("150.00"), unit_cost=Decimal("90.00"), subtotal=Decimal("150.00"))

    # Abandoned Cart (Pending Order)
    order_pending = Order.objects.create(
        user=user3,
        status=OrderStatus.PENDING,
        total=Decimal("80.00"),
        start_date=now - timedelta(days=2),
    )
    OrderItem.objects.create(order=order_pending, item=mouse, quantity=1, unit_price=Decimal("80.00"), unit_cost=Decimal("40.00"), subtotal=Decimal("80.00"))

    # Comments / Reviews
    Comments.objects.create(user=user1, item=laptop, rating=5, body="Increíble laptop para programar y jugar, muy rápida!", likes=10)
    Comments.objects.create(user=user2, item=laptop, rating=4, body="Muy buena calidad y construcción de aluminio.", likes=3)
    Comments.objects.create(user=user3, item=mouse, rating=1, body="Llegó con retraso y no me gustó el click.", likes=0)

    return {
        'laptop': laptop,
        'mouse': mouse,
        'keyboard': keyboard,
        'user1': user1,
        'user2': user2,
        'user3': user3,
    }


@pytest.mark.django_db
class TestAIEngineInternalEndpoints:
    """
    Test suite for internal AI engine endpoints and business intelligence services.
    """
    SECRET_HEADER = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}

    def test_dynamic_sales_query_endpoint(self, client, ai_engine_dataset):
        """
        GET /api/v1/internal/analytics/query/ aggregates sales by dimension.
        """
        response = client.get('/api/v1/internal/analytics/query/?group_by=category', **self.SECRET_HEADER)
        assert response.status_code == 200
        data = response.json()
        assert 'query_metadata' in data
        assert 'summary' in data
        assert 'data' in data
        assert data['summary']['total_revenue'] > 0
        assert data['summary']['total_orders'] >= 2
        assert len(data['data']) >= 1

    def test_inventory_health_endpoint(self, client, ai_engine_dataset):
        """
        GET /api/v1/internal/inventory/health/ computes valuation and stockout risks.
        """
        response = client.get('/api/v1/internal/inventory/health/', **self.SECRET_HEADER)
        assert response.status_code == 200
        data = response.json()
        assert 'metrics' in data
        assert data['metrics']['total_active_skus'] == 3
        assert data['metrics']['out_of_stock_count'] == 1  # mouse has stock=0
        assert data['metrics']['low_stock_count'] >= 1     # laptop has stock=5 <= minimum_stock=10
        assert 'inventory_valuation' in data
        assert data['inventory_valuation']['total_retail_value'] > 0
        assert len(data['critical_items']) >= 1
        assert data['critical_items'][0]['stock_status'] == 'OUT_OF_STOCK'

    def test_margins_endpoint(self, client, ai_engine_dataset):
        """
        GET /api/v1/internal/analytics/margins/ calculates profit margins by product & category.
        """
        response = client.get('/api/v1/internal/analytics/margins/?dimension=product', **self.SECRET_HEADER)
        assert response.status_code == 200
        data = response.json()
        assert 'overall_margin' in data
        assert data['overall_margin']['overall_margin_pct'] > 0
        assert len(data['results']) >= 1
        for res in data['results']:
            assert 'gross_margin_pct' in res
            assert 'gross_profit' in res

    def test_margins_endpoint_with_date_range(self, client, ai_engine_dataset):
        """
        GET /api/v1/internal/analytics/margins/ filters accurately by date_from and date_to.
        """
        now = timezone.now()
        date_from = (now - timedelta(days=6)).strftime('%Y-%m-%d')
        date_to = (now - timedelta(days=4)).strftime('%Y-%m-%d')

        # Query matching only order1 (laptop, 5 days ago)
        url = f'/api/v1/internal/analytics/margins/?dimension=product&date_from={date_from}&date_to={date_to}'
        response = client.get(url, **self.SECRET_HEADER)
        assert response.status_code == 200
        data = response.json()
        assert data['date_from'] == date_from
        assert data['date_to'] == date_to
        assert data['overall_margin']['total_revenue'] == 2000.00
        assert data['overall_margin']['total_cost'] == 1200.00
        assert data['overall_margin']['total_gross_profit'] == 800.00
        assert len(data['results']) == 1
        assert data['results'][0]['title'] == 'Gaming Laptop ROG Strix RTX'

        # Query in an empty date range
        url_empty = '/api/v1/internal/analytics/margins/?dimension=category&date_from=2020-01-01&date_to=2020-01-31'
        response_empty = client.get(url_empty, **self.SECRET_HEADER)
        assert response_empty.status_code == 200
        data_empty = response_empty.json()
        assert data_empty['date_from'] == '2020-01-01'
        assert data_empty['date_to'] == '2020-01-31'
        assert data_empty['overall_margin']['total_revenue'] == 0.0
        assert len(data_empty['results']) == 0

    def test_margins_service_direct_date_filtering(self, ai_engine_dataset):
        """
        Direct service unit test verifying calculate_margins_service with category dimension and date ranges.
        """
        from apps.analytics.services import calculate_margins_service

        now = timezone.now()
        date_from = (now - timedelta(days=20)).strftime('%Y-%m-%d')
        date_to = (now - timedelta(days=10)).strftime('%Y-%m-%d')

        # Matches order2 (keyboard, 15 days ago)
        result = calculate_margins_service(dimension='category', date_from=date_from, date_to=date_to)
        assert result['date_from'] == date_from
        assert result['date_to'] == date_to
        assert result['overall_margin']['total_revenue'] == 150.00
        assert len(result['results']) == 1
        assert result['results'][0]['category'] == 'Electronics'

    def test_dynamic_sales_query_service_date_filtering(self, ai_engine_dataset):
        """
        Direct service unit test verifying dynamic_sales_query_service with date ranges.
        """
        from apps.analytics.services import dynamic_sales_query_service

        now = timezone.now()
        date_from = (now - timedelta(days=6)).strftime('%Y-%m-%d')
        date_to = (now - timedelta(days=4)).strftime('%Y-%m-%d')

        result = dynamic_sales_query_service(date_from=date_from, date_to=date_to, group_by='category')
        assert result['query_metadata']['date_from'] == date_from
        assert result['query_metadata']['date_to'] == date_to
        assert result['summary']['total_revenue'] == 2000.00
        assert result['summary']['total_orders'] == 1
        assert len(result['data']) == 1
        assert result['data'][0]['dimension'] == 'Electronics'

    def test_funnel_endpoint(self, client, ai_engine_dataset):
        """
        GET /api/v1/internal/analytics/funnel/ calculates cart abandonment and promotions ROI.
        """
        response = client.get('/api/v1/internal/analytics/funnel/?period=last_30_days', **self.SECRET_HEADER)
        assert response.status_code == 200
        data = response.json()
        assert 'funnel_metrics' in data
        assert data['funnel_metrics']['total_orders'] >= 4
        assert data['funnel_metrics']['pending_orders'] == 1
        assert data['funnel_metrics']['cart_abandonment_rate_pct'] > 0
        assert len(data['abandoned_products_ranking']) >= 1
        assert len(data['coupon_effectiveness']) >= 1
        assert len(data['payment_methods_breakdown']) >= 1

    def test_reviews_summary_endpoint(self, client, ai_engine_dataset):
        """
        GET /api/v1/internal/catalog/reviews-summary/ computes sentiment and star distribution.
        """
        response = client.get('/api/v1/internal/catalog/reviews-summary/', **self.SECRET_HEADER)
        assert response.status_code == 200
        data = response.json()
        assert data['summary']['total_reviews'] == 3
        assert data['summary']['average_rating'] > 0
        assert data['summary']['rating_distribution']['5_stars'] == 1
        assert len(data['recent_negative_feedback']) == 1
        assert len(data['recent_positive_feedback']) == 2

    def test_customer_insights_endpoint(self, client, ai_engine_dataset):
        """
        GET /api/v1/internal/customers/insights/ provides RFM segments and geographic distribution.
        """
        response = client.get('/api/v1/internal/customers/insights/', **self.SECRET_HEADER)
        assert response.status_code == 200
        data = response.json()
        assert data['summary']['total_customers'] >= 2
        assert 'segment_counts' in data['summary']
        assert len(data['geographic_distribution']['by_country']) >= 1
        assert len(data['top_customers']) >= 1

    def test_semantic_search_endpoint(self, client, ai_engine_dataset):
        """
        POST /api/v1/internal/catalog/semantic-search/ expands conceptual queries like 'laptop para programar'.
        """
        payload = {'query_text': 'laptop para programar desarrollo gamer', 'limit': 5}
        response = client.post(
            '/api/v1/internal/catalog/semantic-search/',
            data=payload,
            content_type='application/json',
            **self.SECRET_HEADER
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data['intents_detected']) >= 1
        assert len(data['items']) >= 1
        assert 'Gaming Laptop ROG Strix RTX' in data['items'][0]['title']

    def test_sql_sandbox_safe_select(self, client, ai_engine_dataset):
        """
        POST /api/v1/internal/query/raw-read/ securely executes read-only SELECT.
        """
        payload = {'query': 'SELECT title, price, stock FROM product_item ORDER BY price DESC;'}
        response = client.post(
            '/api/v1/internal/query/raw-read/',
            data=payload,
            content_type='application/json',
            **self.SECRET_HEADER
        )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['row_count'] >= 3
        assert 'title' in data['columns']
        assert 'execution_time_ms' in data

    def test_sql_sandbox_rejects_mutations(self, client, ai_engine_dataset):
        """
        POST /api/v1/internal/query/raw-read/ strictly rejects INSERT, UPDATE, DELETE, DROP, etc.
        """
        mutations = [
            "DELETE FROM product_item WHERE id = 1;",
            "UPDATE product_item SET price = 0;",
            "DROP TABLE product_item;",
            "INSERT INTO product_item (title) VALUES ('Hacked');",
            "TRUNCATE TABLE product_order;",
            "SELECT * FROM product_item; DELETE FROM product_order;",
        ]
        for malicious_sql in mutations:
            response = client.post(
                '/api/v1/internal/query/raw-read/',
                data={'query': malicious_sql},
                content_type='application/json',
                **self.SECRET_HEADER
            )
            assert response.status_code == 400
            assert response.json().get('error') in ['Forbidden SQL Keyword', 'Bad Request']
