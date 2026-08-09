from decimal import Decimal
from django.conf import settings
from django.db import models
from django.shortcuts import reverse
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator


LABEL_CHOICES = (
    ('P', 'primary'),
    ('S', 'secondary'),
    ('D', 'danger')
)


class OrderStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Payment'
    PAID = 'PAID', 'Paid'
    SHIPPED = 'SHIPPED', 'Shipped'
    DELIVERED = 'DELIVERED', 'Delivered'
    CANCELED = 'CANCELED', 'Canceled'


class PaymentMethod(models.TextChoices):
    CREDIT_CARD = 'CREDIT_CARD', 'Credit Card'
    DEBIT_CARD = 'DEBIT_CARD', 'Debit Card'
    TRANSFER = 'TRANSFER', 'Bank Transfer'
    CASH = 'CASH', 'Cash'


class Brand(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class Supplier(models.Model):
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.country})"


class Item(models.Model):
    title = models.CharField(max_length=100)
    description = models.CharField(max_length=500, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.IntegerField(default=0)
    minimum_stock = models.IntegerField(default=0)

    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='items')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='items')
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='items')

    label = models.CharField(choices=LABEL_CHOICES, max_length=5, null=True, blank=True)
    slug = models.SlugField(unique=True, blank=True)
    img = models.ImageField(upload_to='products/', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.title and not self.slug:
            base_slug = slugify(self.title) or 'product'
            slug = base_slug
            counter = 1
            while Item.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("product:product", kwargs={'slug': self.slug})

    def get_add_to_cart_url(self):
        return reverse("product:add_to_cart", kwargs={'slug': self.slug})

    def get_remove_single_from_cart_url(self):
        return reverse("product:remove_single_cart", kwargs={'slug': self.slug})

    def get_remove_from_cart_url(self):
        return reverse("product:remove-from-cart", kwargs={'slug': self.slug})

    def get_edit_product_url(self):
        return reverse("product:edit_product", kwargs={'slug': self.slug})


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    description = models.CharField(max_length=300, null=True, blank=True)
    image = models.ImageField(upload_to='profile_image/', blank=True, null=True)
    address_line = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    province = models.CharField(max_length=100, null=True, blank=True)
    zip_code = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True, default='Argentina')
    birth_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.user.username if self.user else "Profile"

    def is_international(self):
        if not self.country:
            return False
        return self.country.strip().lower() not in ['argentina', 'ar']

    def get_profile_url(self):
        return reverse("product:edit_profile", kwargs={'username': self.user.username})


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices, default=PaymentMethod.CREDIT_CARD, null=True, blank=True)
    discount_code = models.CharField(max_length=50, null=True, blank=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    start_date = models.DateTimeField(auto_now_add=True)
    ordered_date = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username} ({self.status})"

    def get_items_subtotal(self):
        return sum(item.subtotal for item in self.items.all())

    def recalculate_shipping_cost(self):
        try:
            if hasattr(self.user, 'profile') and self.user.profile and self.user.profile.is_international():
                self.shipping_cost = Decimal('2500.00')
            else:
                self.shipping_cost = Decimal('500.00')
        except Exception:
            self.shipping_cost = Decimal('500.00')
        return self.shipping_cost

    def recalculate_discount(self):
        subtotal = self.get_items_subtotal()
        if self.discount_code in ['DESC10', 'PROMO10']:
            self.discount = (subtotal * Decimal('0.10')).quantize(Decimal('0.01'))
        elif self.discount_code in ['OFF500', 'DESCUENTO']:
            self.discount = min(Decimal('500.00'), subtotal)
        return self.discount

    def calculate_total(self):
        subtotal_sum = self.get_items_subtotal()
        self.recalculate_shipping_cost()
        self.recalculate_discount()
        self.total = max(Decimal('0.00'), subtotal_sum + self.shipping_cost - self.discount)
        return self.total

    def get_total_price(self):
        return self.calculate_total()

    def get_total_item_count(self):
        return sum(order_item.quantity for order_item in self.items.all())


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', null=True, blank=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.quantity} x {self.item.title}"

    def save(self, *args, **kwargs):
        if (self.unit_price is None or self.unit_price == 0) and self.item:
            if self.item.price != 0 or self.unit_price is None:
                self.unit_price = self.item.price
        if (self.unit_cost is None or self.unit_cost == 0) and self.item:
            if self.item.cost != 0 or self.unit_cost is None:
                self.unit_cost = self.item.cost
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def get_total_item_price(self):
        return self.subtotal


class Comments(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='comments', null=True, blank=True)
    body = models.TextField()
    rating = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    date_added = models.DateTimeField(auto_now_add=True)
    likes = models.IntegerField(default=0)

    class Meta:
        verbose_name_plural = 'Comments'
        unique_together = ('user', 'item')

    def __str__(self):
        return f"Comment by {self.user.username} on {self.item.title}"