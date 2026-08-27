"""
apps.catalog.models

Catalog domain models: Category, Brand, Supplier, Item, Comments.
Maintains exact db_table mappings to ensure 100% database backwards-compatibility.
"""

import hashlib

from decimal import Decimal
from django.conf import settings
from django.db import models
from django.shortcuts import reverse
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator, MaxLengthValidator

from pgvector.django import VectorField, HnswIndex


LABEL_CHOICES = (
    ('P', 'primary'),
    ('S', 'secondary'),
    ('D', 'danger')
)


EMBEDDING_DIM = 768
EMBEDDING_MODEL_NAME = "gemini-embedding-2"   # fallback: "gemini-embedding-001"
EMBEDDING_TEXT_VERSION = 1  # bump this to force a full catalog re-embed


def build_embedding_text(item):
    """Concatenate the fields that carry real semantic signal about a product.

    Deliberately excludes item.supplier (Faker-generated logistics data, not
    a real product attribute) and item.label (a UI badge indicator —
    'primary'/'secondary'/'danger' — not a semantic product attribute; see
    LABEL_CHOICES above). Including either would inject noise into the
    embedding rather than signal.
    """
    parts = [
        item.title, item.title,  # repeated: weighs the title more heavily
        (item.description or ""),
        (item.category.name if item.category_id else ""),
        (item.brand.name if item.brand_id else ""),
    ]
    return " | ".join(p.strip() for p in parts if p and p.strip())[:6000]


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
    title = models.CharField(max_length=300)
    description = models.TextField(null=True, blank=True, validators=[MaxLengthValidator(4000)])
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.IntegerField(default=0)
    minimum_stock = models.IntegerField(default=0)

    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='items')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='items')
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='items')

    label = models.CharField(choices=LABEL_CHOICES, max_length=5, null=True, blank=True)
    external_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
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


class ItemEmbedding(models.Model):
    item = models.OneToOneField(
        Item, on_delete=models.CASCADE, related_name="embedding", primary_key=True
    )
    vector = VectorField(dimensions=EMBEDDING_DIM)
    content_hash = models.CharField(max_length=64)  # sha256(build_embedding_text(item))
    text_version = models.PositiveSmallIntegerField(default=EMBEDDING_TEXT_VERSION)
    model_name = models.CharField(max_length=64, default=EMBEDDING_MODEL_NAME)
    source_updated_at = models.DateTimeField()

    class Meta:
        db_table = "product_item_embedding"
        # Declared here so `makemigrations` sees model state and migration-graph
        # state agree (see the Phase 1 migration's SeparateDatabaseAndState block,
        # which mirrors this same index in both `state_operations` and
        # `database_operations`). The actual CREATE INDEX ... USING hnsw DDL is
        # still gated to PostgreSQL only, at the migration-operation level, via
        # ConditionalAddIndex -- SQLite never executes it.
        indexes = [
            HnswIndex(
                name="item_embedding_hnsw_cos",
                fields=["vector"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]


class ProductAttribute(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="attributes")
    name = models.CharField(max_length=40)    # "color", "size", "material", "gender", "brand"
    value = models.CharField(max_length=100)  # "red", "42", "leather", ...

    class Meta:
        db_table = "product_item_attribute"
        indexes = [models.Index(fields=["name", "value"])]


class EmbeddingSyncTask(models.Model):
    """Outbox-pattern task queue: rows here represent catalog items whose
    embedding needs to be (re)computed by the Chatbot-Engine-Gateway
    microservice. Created either by the `queue_embedding_sync` post_save
    signal (real-time single-item edits) or in bulk by the analytics
    dataset generator (full catalog regeneration).

    The Gateway polls GET .../embeddings/pending/ to claim PENDING tasks
    (atomically flipped to PROCESSING at claim time -- see
    apps.catalog.rag_service.get_pending_embedding_tasks_service), computes
    the embedding, then reports back via .../embeddings/upsert/ (-> DONE) or
    .../embeddings/mark-error/ (-> ERROR).
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        DONE = "done", "Done"
        ERROR = "error", "Error"

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="embedding_sync_tasks")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    content_hash = models.CharField(max_length=64)
    error_message = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalog_embedding_sync_task"
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"EmbeddingSyncTask(item={self.item_id}, status={self.status})"
