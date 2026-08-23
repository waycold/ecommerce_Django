from decimal import Decimal
import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from apps.catalog.models import Brand, Category, Item, Supplier
from apps.orders.models import Order, OrderItem, OrderStatus


@pytest.fixture
def analytics_sample_data(db):
    """
    Creates a realistic dataset with categories, products, paid and pending orders
    for testing business metrics and KPI calculations.
    """
    now = timezone.now()

    user_1 = User.objects.create_user(username="analytics_customer_1", password="password123")
    user_2 = User.objects.create_user(username="analytics_customer_2", password="password123")

    cat_tech = Category.objects.create(name="Electronics")
    cat_home = Category.objects.create(name="Home")

    brand = Brand.objects.create(name="TechCorp")
    supplier = Supplier.objects.create(name="FastShip", country="USA")

    item_1 = Item.objects.create(
        title="Smart Display 10",
        price=Decimal("200.00"),
        cost=Decimal("120.00"),
        stock=20,
        category=cat_tech,
        brand=brand,
        supplier=supplier,
        is_active=True,
    )

    item_2 = Item.objects.create(
        title="Coffee Brewer",
        price=Decimal("100.00"),
        cost=Decimal("50.00"),
        stock=15,
        category=cat_home,
        brand=brand,
        supplier=supplier,
        is_active=True,
    )

    # Paid Order 1 by user 1 (Total: $400)
    order_1 = Order.objects.create(
        user=user_1,
        status=OrderStatus.PAID,
        total=Decimal("400.00"),
        ordered_date=now,
    )
    OrderItem.objects.create(
        order=order_1,
        item=item_1,
        quantity=2,
        unit_price=Decimal("200.00"),
        unit_cost=Decimal("120.00"),
        subtotal=Decimal("400.00"),
    )

    # Paid Order 2 by user 2 (Total: $100)
    order_2 = Order.objects.create(
        user=user_2,
        status=OrderStatus.PAID,
        total=Decimal("100.00"),
        ordered_date=now,
    )
    OrderItem.objects.create(
        order=order_2,
        item=item_2,
        quantity=1,
        unit_price=Decimal("100.00"),
        unit_cost=Decimal("50.00"),
        subtotal=Decimal("100.00"),
    )

    # Pending Cart (Abandoned Cart)
    order_pending = Order.objects.create(
        user=user_1,
        status=OrderStatus.PENDING,
        total=Decimal("200.00"),
        ordered_date=now,
    )
    OrderItem.objects.create(
        order=order_pending,
        item=item_1,
        quantity=1,
        unit_price=Decimal("200.00"),
        unit_cost=Decimal("120.00"),
        subtotal=Decimal("200.00"),
    )

    return {
        'user_1': user_1,
        'user_2': user_2,
        'item_1': item_1,
        'item_2': item_2,
        'order_1': order_1,
        'order_2': order_2,
        'order_pending': order_pending,
    }


@pytest.mark.django_db
class TestAnalyticsContract:
    """
    Test suite for Contract 3: Business Analytics & Metrics API (GET /api/v1/internal/analytics/metrics/).
    """

    METRICS_URL = '/api/v1/internal/analytics/metrics/'

    def test_analytics_metrics_unauthorized_missing_secret(self, client):
        """
        Requesting analytics metrics without X-Internal-Secret returns 401 Unauthorized.
        """
        response = client.get(self.METRICS_URL)
        assert response.status_code == 401
        data = response.json()
        assert data.get('error') == 'Unauthorized'

    def test_analytics_metrics_unauthorized_wrong_secret(self, client):
        """
        Requesting analytics metrics with an invalid secret returns 401 Unauthorized.
        """
        response = client.get(
            self.METRICS_URL,
            HTTP_X_INTERNAL_SECRET='invalid-secret-key'
        )
        assert response.status_code == 401
        data = response.json()
        assert data.get('error') == 'Unauthorized'

    def test_analytics_metrics_disallowed_methods(self, client):
        """
        POST, PUT, DELETE methods on /api/v1/internal/analytics/metrics/ return 405 Method Not Allowed.
        """
        secret = settings.INTERNAL_API_SECRET

        response_post = client.post(self.METRICS_URL, HTTP_X_INTERNAL_SECRET=secret)
        assert response_post.status_code == 405

        response_put = client.put(self.METRICS_URL, HTTP_X_INTERNAL_SECRET=secret)
        assert response_put.status_code == 405

        response_delete = client.delete(self.METRICS_URL, HTTP_X_INTERNAL_SECRET=secret)
        assert response_delete.status_code == 405

    def test_analytics_metrics_default_overview(self, client, analytics_sample_data):
        """
        GET without query parameter returns default overview/kpis payload with 200 OK.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(self.METRICS_URL, HTTP_X_INTERNAL_SECRET=secret)
        assert response.status_code == 200
        data = response.json()

        assert 'monthly_revenue' in data
        assert 'avg_order_value' in data
        assert 'current_month' in data
        # Check either monthly_orders or monthly_orders_count
        assert ('monthly_orders' in data or 'monthly_orders_count' in data)
        assert ('active_customers' in data or 'active_customers_count' in data)
        assert ('abandoned_carts' in data or 'abandoned_carts_count' in data)

    def test_analytics_metrics_explicit_overview_and_kpis(self, client, analytics_sample_data):
        """
        GET with ?metric_type=overview and ?metric_type=kpis returns 200 OK.
        """
        secret = settings.INTERNAL_API_SECRET

        res_overview = client.get(f"{self.METRICS_URL}?metric_type=overview", HTTP_X_INTERNAL_SECRET=secret)
        assert res_overview.status_code == 200
        data_overview = res_overview.json()
        assert data_overview.get('metric_type') == 'overview'

        res_kpis = client.get(f"{self.METRICS_URL}?metric_type=kpis", HTTP_X_INTERNAL_SECRET=secret)
        assert res_kpis.status_code == 200
        data_kpis = res_kpis.json()
        assert data_kpis.get('metric_type') == 'kpis'

    def test_analytics_metrics_forecast_and_sales_trend(self, client, analytics_sample_data):
        """
        GET with ?metric_type=forecast and ?metric_type=sales_trend returns 200 OK and time-series projections.
        """
        secret = settings.INTERNAL_API_SECRET

        response_forecast = client.get(f"{self.METRICS_URL}?metric_type=forecast", HTTP_X_INTERNAL_SECRET=secret)
        assert response_forecast.status_code == 200
        data_forecast = response_forecast.json()
        assert 'historical_trend' in data_forecast
        assert 'forecast_3_months' in data_forecast
        assert 'next_month_projected' in data_forecast
        assert 'mom_growth_pct' in data_forecast

        response_trend = client.get(f"{self.METRICS_URL}?metric_type=sales_trend", HTTP_X_INTERNAL_SECRET=secret)
        assert response_trend.status_code == 200
        data_trend = response_trend.json()
        assert 'historical_trend' in data_trend

    def test_analytics_metrics_category_distribution(self, client, analytics_sample_data):
        """
        GET with ?metric_type=category_distribution returns 200 OK and category breakdown.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(f"{self.METRICS_URL}?metric_type=category_distribution", HTTP_X_INTERNAL_SECRET=secret)
        assert response.status_code == 200
        data = response.json()
        assert data.get('metric_type') == 'category_distribution'
        assert 'categories' in data
        assert isinstance(data['categories'], list)
        assert 'total_category_revenue' in data

    def test_analytics_metrics_top_products(self, client, analytics_sample_data):
        """
        GET with ?metric_type=top_products returns 200 OK and ranking of products with revenue and units.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(f"{self.METRICS_URL}?metric_type=top_products", HTTP_X_INTERNAL_SECRET=secret)
        assert response.status_code == 200
        data = response.json()
        assert data.get('metric_type') == 'top_products'
        assert 'top_products' in data
        assert isinstance(data['top_products'], list)
        assert len(data['top_products']) > 0

        first_product = data['top_products'][0]
        assert 'product_id' in first_product or 'item__id' in first_product or 'id' in first_product
        assert 'title' in first_product
        assert 'total_units_sold' in first_product
        assert 'total_revenue_generated' in first_product

    def test_analytics_metrics_all(self, client, analytics_sample_data):
        """
        GET with ?metric_type=all returns consolidated metrics containing overview, forecast, categories, top_products.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(f"{self.METRICS_URL}?metric_type=all", HTTP_X_INTERNAL_SECRET=secret)
        assert response.status_code == 200
        data = response.json()
        assert data.get('metric_type') == 'all'
        assert 'overview' in data
        assert 'forecast' in data
        assert 'category_distribution' in data
        assert 'top_products' in data

    def test_analytics_metrics_invalid_metric_type(self, client):
        """
        GET with invalid metric_type returns 400 Bad Request.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(f"{self.METRICS_URL}?metric_type=invalid_metric_xyz", HTTP_X_INTERNAL_SECRET=secret)
        assert response.status_code == 400
        data = response.json()
        assert data.get('error') == 'Bad Request'

    def test_analytics_metrics_calculations_accuracy(self, client, analytics_sample_data):
        """
        Verify that KPI calculations (monthly_revenue, monthly_orders, avg_order_value, abandoned_carts)
        accurately reflect database orders.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.get(f"{self.METRICS_URL}?metric_type=overview", HTTP_X_INTERNAL_SECRET=secret)
        assert response.status_code == 200
        data = response.json()

        # Expected: Order 1 ($400) + Order 2 ($100) = $500 monthly revenue
        assert data['monthly_revenue'] == 500.0

        # Expected: 2 paid orders
        monthly_orders = data.get('monthly_orders', data.get('monthly_orders_count'))
        assert monthly_orders == 2

        # Expected: $500 / 2 orders = $250.0 average order value
        assert data['avg_order_value'] == 250.0

        # Expected: 2 distinct active customers (user_1 and user_2)
        active_customers = data.get('active_customers', data.get('active_customers_count'))
        assert active_customers == 2

        # Expected: 1 abandoned cart (order_pending)
        abandoned_carts = data.get('abandoned_carts', data.get('abandoned_carts_count'))
        assert abandoned_carts == 1

        # Star product should be Smart Display 10 (2 units sold, $400 generated)
        star = data.get('top_product_star')
        assert star is not None
        assert star['title'] == "Smart Display 10"
        assert star['total_units_sold'] == 2
        assert star['total_revenue_generated'] == 400.0
