from django.contrib import admin
from apps.catalog.models import Brand, Category, Supplier, Item, Comments, EmbeddingSyncTask


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at', 'updated_at')
    search_fields = ('name',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at', 'updated_at')
    search_fields = ('name',)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'country', 'created_at', 'updated_at')
    search_fields = ('name', 'country')


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'price', 'cost', 'stock', 'minimum_stock', 'category', 'brand', 'supplier', 'is_active')
    list_filter = ('category', 'brand', 'supplier', 'is_active')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Comments)
class CommentsAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'item', 'date_added', 'likes')
    search_fields = ('user__username', 'body', 'item__title')


@admin.register(EmbeddingSyncTask)
class EmbeddingSyncTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'item', 'status', 'content_hash', 'created_at', 'updated_at')
    list_filter = ('status',)
    search_fields = ('item__title', 'error_message')
