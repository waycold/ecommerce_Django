from django.conf import settings
from django.db import models
from django.shortcuts import reverse
from django.contrib.auth.models import User
from django.utils.text import slugify

CATEGORY_CHOICES = (
    ('CPU', 'CPU'),
    ('RAM', 'RAM'),
    ('GPU', 'GPU')
)

LABEL_CHOICES = (
    ('P', 'primary'),
    ('S', 'secondary'),
    ('D', 'danger')
)

ORDER_STATUS_CHOICES = (
    ('ABANDONED', 'Carrito Abandonado'),
    ('PENDING', 'Pendiente de Pago'),
    ('PAID', 'Pagado'),
    ('SHIPPED', 'Enviado'),
    ('DELIVERED', 'Entregado'),
    ('CANCELED', 'Cancelado'),
)

class Item(models.Model):
    title = models.CharField(max_length=100) # CORREGIDO: title a title
    description = models.CharField(max_length=500, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=0)
    
    cost = models.DecimalField(max_digits=10, decimal_places=0, default=0) 
    
    category = models.CharField(choices=CATEGORY_CHOICES, max_length=5)
    label = models.CharField(choices=LABEL_CHOICES, max_length=5, null=True, blank=True)
    slug = models.SlugField(unique=True, blank=True)
    img = models.ImageField(upload_to='products/', null=True)
    
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.title:
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

    def get_delete_product_url(self):
        return reverse("product:delete_product", kwargs={'slug': self.slug})


class OrderItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    ordered = models.BooleanField(default=False)
    quantity = models.IntegerField(default=1)
    
    historical_price = models.DecimalField(max_digits=10, decimal_places=0, default=0)

    def __str__(self):
        return f"{self.quantity} of {self.item.title}"

    def get_total_item_price(self):
        if self.ordered and self.historical_price > 0:
            return self.quantity * self.historical_price
        return self.quantity * self.item.price


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    items = models.ManyToManyField(OrderItem)
    
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='PENDING')
    
    start_date = models.DateTimeField(auto_now_add=True)
    ordered_date = models.DateTimeField(null=True, blank=True) # Permite nulos para carritos activos
    ordered = models.BooleanField(default=False)
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.username

    def get_total_price(self):
        total = 0
        for order_item in self.items.all():
            total += order_item.get_total_item_price()
        return total

    def get_total_item_count(self):
        return sum(order_item.quantity for order_item in self.items.all())


class Profile(models.Model):
    username = models.ForeignKey(User, on_delete=models.CASCADE)
    user = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.DecimalField(decimal_places=0, max_digits=10, null=True, blank=True)
    description = models.CharField(max_length=300, null=True, blank=True)
    image = models.ImageField(upload_to='profile_image/', blank=True, null=True)

    def __str__(self):
        return self.username.username

    def get_profile_url(self):
        return reverse("product:edit_profile", kwargs={'username': self.username.username})


class Comments(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField()
    
    date_added = models.DateTimeField(auto_now_add=True)
    
    url = models.URLField(max_length=200)
    likes = models.IntegerField(default=0)
    image_perfil = models.ImageField(upload_to='profile_image/', blank=True, null=True, default='profile_image/default.jpg')

    def __str__(self):
        return f"comment of {self.user} in {self.url}"