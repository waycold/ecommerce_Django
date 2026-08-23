import random
import string
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from apps.catalog.models import Item, Category, Brand, Supplier
from apps.orders.models import Profile, Order, OrderItem, OrderStatus, PaymentMethod


class OrdersModelTests(TestCase):
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
        self.user = User.objects.create_user(username="testbuyer", password="password123")
        self.profile = Profile.objects.create(user=self.user, phone="11223344", city="New York")

    def test_order_creation_and_total(self):
        order = Order.objects.create(user=self.user, status=OrderStatus.PENDING)
        order_item = OrderItem.objects.create(order=order, item=self.item, quantity=2)
        self.assertEqual(order_item.subtotal, 900.00)
        self.assertEqual(order.calculate_total(), 1400.00)  # 900 subtotal + 500 domestic shipping
        self.assertEqual(order.get_total_item_count(), 2)

    def test_discount_recalculation(self):
        order = Order.objects.create(user=self.user, status=OrderStatus.PENDING, shipping_cost=500.00)
        order_item = OrderItem.objects.create(order=order, item=self.item, quantity=2)
        order.discount_code = 'DESC10'
        # 10% of 900 = 90, total = 900 + 500 - 90 = 1310
        self.assertEqual(order.calculate_total(), 1310.00)
        self.assertEqual(order.discount, 90.00)

        # Add 1 more item (subtotal 1350)
        order_item.quantity = 3
        order_item.save()
        # 10% of 1350 = 135, total = 1350 + 500 - 135 = 1715
        self.assertEqual(order.calculate_total(), 1715.00)
        self.assertEqual(order.discount, 135.00)

    def test_international_shipping_calculation(self):
        self.profile.country = "Germany"
        self.profile.save()
        order = Order.objects.create(user=self.user, status=OrderStatus.PENDING)
        order_item = OrderItem.objects.create(order=order, item=self.item, quantity=1)
        self.assertEqual(order.recalculate_shipping_cost(), Decimal('2500.00'))
        self.assertEqual(order.calculate_total(), Decimal('2950.00'))
