from django.contrib import admin
from apps.orders.models import OrderItem, Order, Profile


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
