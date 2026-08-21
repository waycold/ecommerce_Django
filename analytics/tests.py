from django.test import TestCase
from django.contrib.auth.models import User
from product.models import Order, OrderItem, Item, Category, Brand, Supplier, OrderStatus
from analytics.services import get_dashboard_kpis, get_forecast_data, get_simulator_config


class AnalyticsTestCase(TestCase):
    def setUp(self):
        # Create normal user & staff user
        self.user = User.objects.create_user(username="normaluser", password="password123")
        self.staff = User.objects.create_user(username="staffuser", password="password123", is_staff=True)

        # Create sample catalog data
        self.category = Category.objects.create(name="Tech")
        self.brand = Brand.objects.create(name="BrandA")
        self.supplier = Supplier.objects.create(name="SupA", country="Argentina")

        self.item1 = Item.objects.create(
            title="Laptop Pro", price=1000.00, cost=600.00, stock=10,
            category=self.category, brand=self.brand, supplier=self.supplier
        )
        self.item2 = Item.objects.create(
            title="Wireless Mouse", price=50.00, cost=20.00, stock=50,
            category=self.category, brand=self.brand, supplier=self.supplier
        )

        # Create sample orders
        self.paid_order = Order.objects.create(user=self.user, status=OrderStatus.PAID, total=1050.00)
        OrderItem.objects.create(order=self.paid_order, item=self.item1, quantity=1, unit_price=1000.00, unit_cost=600.00, subtotal=1000.00)
        OrderItem.objects.create(order=self.paid_order, item=self.item2, quantity=1, unit_price=50.00, unit_cost=20.00, subtotal=50.00)

        self.pending_order = Order.objects.create(user=self.user, status=OrderStatus.PENDING, total=50.00)
        OrderItem.objects.create(order=self.pending_order, item=self.item2, quantity=1, unit_price=50.00, unit_cost=20.00, subtotal=50.00)

    def test_security_access_restriction(self):
        # Anonymous user redirect
        response_anon = self.client.get('/analytics/dashboard/')
        self.assertNotEqual(response_anon.status_code, 200)

        # Non-staff user redirect
        self.client.login(username="normaluser", password="password123")
        response_user = self.client.get('/analytics/dashboard/')
        self.assertNotEqual(response_user.status_code, 200)

        # Staff user allowed on Dashboard
        self.client.login(username="staffuser", password="password123")
        response_staff = self.client.get('/analytics/dashboard/')
        self.assertEqual(response_staff.status_code, 200)
        self.assertContains(response_staff, "Management Dashboard")
        self.assertContains(response_staff, "Forecast & Trends")
        self.assertContains(response_staff, "Data Simulator")

    def test_forecast_view(self):
        self.client.login(username="staffuser", password="password123")
        response = self.client.get('/analytics/forecast/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forecast & Trends")
        self.assertContains(response, "Projected Next Month Revenue")

    def test_simulator_view(self):
        self.client.login(username="staffuser", password="password123")
        response = self.client.get('/analytics/simulator/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Synthetic Data Simulator")
        self.assertContains(response, "Generate Dataset")

    def test_export_excel_endpoint(self):
        self.client.login(username="staffuser", password="password123")
        response = self.client.get('/analytics/export/excel/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertTrue(len(response.content) > 0)

    def test_kpi_service(self):
        kpis = get_dashboard_kpis()
        self.assertEqual(kpis['abandoned_carts_count'], 1)
        self.assertIn('avg_order_value', kpis)
        self.assertIn('monthly_orders_count', kpis)
        self.assertIn('active_customers_count', kpis)
        self.assertTrue(len(kpis['top_products']) > 0)

    def test_forecast_service(self):
        forecast = get_forecast_data()
        self.assertIn('months_labels', forecast)
        self.assertIn('forecast_revenue', forecast)
        self.assertIn('category_labels', forecast)

    def test_simulator_config_api(self):
        self.client.login(username="staffuser", password="password123")
        response = self.client.get('/analytics/api/simulator-config/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('simulation_params', data)
        self.assertIn('product_tiers', data)

    def test_generation_progress_api(self):
        self.client.login(username="staffuser", password="password123")
        response = self.client.get('/analytics/api/generation-progress/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('progress_pct', data)
        self.assertIn('current_step', data)

    def test_ai_chat_view_security_and_rendering(self):
        # Anonymous redirect
        res_anon = self.client.get('/analytics/chat/')
        self.assertNotEqual(res_anon.status_code, 200)

        # Normal user redirect
        self.client.login(username="normaluser", password="password123")
        res_user = self.client.get('/analytics/chat/')
        self.assertNotEqual(res_user.status_code, 200)

        # Staff user authorized
        self.client.login(username="staffuser", password="password123")
        res_staff = self.client.get('/analytics/chat/')
        self.assertEqual(res_staff.status_code, 200)
        self.assertContains(res_staff, "AI Analytics Assistant")
        self.assertContains(res_staff, "Managerial AI Agent")

