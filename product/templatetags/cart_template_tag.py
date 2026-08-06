from product.models import Order, OrderStatus
from django import template

register = template.Library()


@register.filter()
def cart_item_count(user):
    if user.is_authenticated:
        order = Order.objects.filter(user=user, status=OrderStatus.PENDING).first()
        if order:
            return order.get_total_item_count()
    return 0
