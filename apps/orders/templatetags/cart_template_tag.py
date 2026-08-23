from django import template
from apps.orders.models import Order, OrderStatus

register = template.Library()


@register.filter()
def cart_item_count(user):
    if user and user.is_authenticated:
        order = Order.objects.filter(user=user, status=OrderStatus.PENDING).first()
        if order:
            return order.get_total_item_count()
    return 0
