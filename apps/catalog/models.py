"""
apps.catalog.models

Catalog domain models: Category, Brand, Supplier, Item, Comments.
Maintains exact db_table mappings to ensure 100% database backwards-compatibility.
"""

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


class Brand(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'product_brand'

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'product_category'
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class Supplier(models.Model):
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'product_supplier'

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

    class Meta:
        db_table = 'product_item'

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
        return reverse("catalog:product", kwargs={'slug': self.slug})

    def get_add_to_cart_url(self):
        return reverse("orders:add_to_cart", kwargs={'slug': self.slug})

    def get_remove_single_from_cart_url(self):
        return reverse("orders:remove_single_cart", kwargs={'slug': self.slug})

    def get_remove_from_cart_url(self):
        return reverse("orders:remove-from-cart", kwargs={'slug': self.slug})

    def get_edit_product_url(self):
        return reverse("catalog:edit_product", kwargs={'slug': self.slug})


class Comments(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='comments', null=True, blank=True)
    body = models.TextField()
    rating = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    date_added = models.DateTimeField(auto_now_add=True)
    likes = models.IntegerField(default=0)

    class Meta:
        db_table = 'product_comments'
        verbose_name_plural = 'Comments'
        unique_together = ('user', 'item')

    def __str__(self):
        item_title = self.item.title if self.item else "Deleted Item"
        return f"Comment by {self.user.username} on {item_title}"
