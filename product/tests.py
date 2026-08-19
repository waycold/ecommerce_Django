from django.test import TestCase
import random
import string
from django.contrib.auth.models import User
from product.models import Profile, Comments, Item, Category, Brand, Supplier, Order, OrderItem, OrderStatus


class ProfileTestCase(TestCase):
    def setUp(self):
        length = random.randint(5, 12)
        self.username = ''.join(random.choice(string.ascii_letters) for _ in range(length))
        self.password = 'pass12345'
        self.test_user = User.objects.create_user(
            username=self.username,
            password=self.password,
        )

    def test_users(self):
        self.assertTrue(self.test_user.is_active)
        self.assertFalse(self.test_user.is_anonymous)
        self.assertFalse(self.test_user.is_staff)
        self.assertFalse(self.test_user.is_superuser)

    def test_login(self):
        login_success = self.client.login(username=self.username, password=self.password)
        self.assertTrue(login_success)

    def test_default_profile_image(self):
        from product.utils import get_profile_image_url
        # Anonymous user
        from django.contrib.auth.models import AnonymousUser
        self.assertIn('default-avatar.svg', get_profile_image_url(AnonymousUser()))
        # Authenticated user without custom image
        self.assertIn('default-avatar.svg', get_profile_image_url(self.test_user))



class ModelsRefactorTestCase(TestCase):
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

    def test_item_creation(self):
        self.assertEqual(self.item.category.name, "CPU")
        self.assertEqual(self.item.brand.name, "Intel")
        self.assertEqual(self.item.supplier.name, "TechCorp")
        self.assertEqual(self.item.slug, "core-i7-13700k")

    def test_order_creation_and_total(self):
        order = Order.objects.create(user=self.user, status=OrderStatus.PENDING)
        order_item = OrderItem.objects.create(order=order, item=self.item, quantity=2)
        self.assertEqual(order_item.subtotal, 900.00)
        self.assertEqual(order.calculate_total(), 1400.00) # 900 subtotal + 500 domestic shipping
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

    def test_stock_validation_and_home_filtering(self):
        out_of_stock_item = Item.objects.create(
            title="Out of Stock GPU",
            price=300.00,
            cost=200.00,
            stock=0,
            is_active=True,
        )
        self.client.login(username="testbuyer", password="password123")

        # Home view should not list out of stock item
        response = self.client.get('/')
        self.assertContains(response, "Core i7 13700K")
        self.assertNotContains(response, "Out of Stock GPU")

        # Try to add out of stock item to cart
        res = self.client.get(out_of_stock_item.get_add_to_cart_url(), follow=True)
        self.assertContains(res, "is out of stock")

    def test_profile_fields(self):
        from datetime import date
        self.profile.address_line = "5th Ave 100"
        self.profile.city = "New York"
        self.profile.province = "NY"
        self.profile.zip_code = "10001"
        self.profile.country = "United States"
        self.profile.birth_date = date(1995, 5, 20)
        self.profile.save()

        self.assertEqual(self.profile.address_line, "5th Ave 100")
        self.assertEqual(self.profile.city, "New York")
        self.assertEqual(self.profile.province, "NY")
        self.assertEqual(self.profile.zip_code, "10001")
        self.assertEqual(self.profile.country, "United States")
        self.assertFalse(self.profile.is_international())
        self.assertEqual(self.profile.birth_date, date(1995, 5, 20))

    def test_international_shipping(self):
        order = Order.objects.create(user=self.user, status=OrderStatus.PENDING)
        order_item = OrderItem.objects.create(order=order, item=self.item, quantity=1)

        # Default country (United States) -> domestic shipping $500.00
        self.assertEqual(order.recalculate_shipping_cost(), 500.00)
        self.assertEqual(order.calculate_total(), 950.00) # 450 + 500

        # Change profile country to Spain -> international shipping $2500.00
        self.profile.country = "Spain"
        self.profile.save()

        self.assertTrue(self.profile.is_international())
        self.assertEqual(order.recalculate_shipping_cost(), 2500.00)
        self.assertEqual(order.calculate_total(), 2950.00) # 450 + 2500

    def test_home_pagination(self):
        # Create 20 active items with stock
        for i in range(20):
            Item.objects.create(
                title=f"Paged Product {i}",
                price=100.00,
                cost=50.00,
                stock=5,
                is_active=True,
            )

        # Page 1 should contain 16 items
        res1 = self.client.get('/?page=1')
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(len(res1.context['items']), 16)

        # Page 2 should contain remaining items (20 + 1 from setUp = 21 items total, page 2 has 5 items)
        res2 = self.client.get('/?page=2')
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(len(res2.context['items']), 5)

    def test_comment_rating_and_uniqueness(self):
        # Create a first review with rating
        Comments.objects.create(
            user=self.user,
            item=self.item,
            body="First review",
            rating=4
        )

        comment = Comments.objects.get(user=self.user, item=self.item)
        self.assertEqual(comment.rating, 4)

        # Enforce unique constraint: trying to create a second comment by same user on same item should fail
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Comments.objects.create(
                user=self.user,
                item=self.item,
                body="Second review"
            )

