from django.test import TestCase
from django.contrib.auth.models import User
from product.models import Order, OrderItem, Item, Category, Brand, Supplier, OrderStatus
from analytics.services import get_dashboard_kpis


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

        # Staff user allowed
        self.client.login(username="staffuser", password="password123")
        response_staff = self.client.get('/analytics/dashboard/')
        self.assertEqual(response_staff.status_code, 200)
        self.assertContains(response_staff, "Management Dashboard")

    def test_export_excel_endpoint(self):
        self.client.login(username="staffuser", password="password123")
        response = self.client.get('/analytics/export/excel/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertTrue(len(response.content) > 0)

    def test_kpi_service(self):
        kpis = get_dashboard_kpis()
        self.assertEqual(kpis['abandoned_carts_count'], 1)
        self.assertTrue(len(kpis['top_products']) > 0)
