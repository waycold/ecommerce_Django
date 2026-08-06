from django.contrib import admin
from product.models import Brand, Category, Supplier, Item, OrderItem, Order, Profile, Comments


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


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'item', 'quantity', 'unit_price', 'unit_cost', 'subtotal')
    list_filter = ('order__status',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'payment_method', 'total', 'start_date', 'ordered_date')
    list_filter = ('status', 'payment_method')
    search_fields = ('user__username',)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'phone', 'city', 'province', 'birth_date')
    search_fields = ('user__username', 'phone', 'city', 'province')


@admin.register(Comments)
class CommentsAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'item', 'date_added', 'likes')
    search_fields = ('user__username', 'body', 'item__title')