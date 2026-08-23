"""
apps/orders/services.py

Business logic and domain service layer for cart operations,
order calculations, discount codes, and checkout processing.
"""

from decimal import Decimal
from typing import Optional, Tuple
from django.contrib.auth.models import User
from django.utils import timezone
from apps.orders.models import Order, OrderItem, OrderStatus, PaymentMethod
from apps.catalog.models import Item
from apps.orders.customer_insights_service import get_customer_insights_service



def get_or_create_active_order(user: User) -> Tuple[Order, bool]:
    """
    Retrieves or creates a PENDING cart order for the user.
    """
    return Order.objects.get_or_create(
        user=user,
        status=OrderStatus.PENDING,
    )


def add_item_to_cart_service(user: User, slug: str) -> Tuple[bool, str]:
    """
    Adds 1 unit of the item specified by slug to the user's active cart.

    Returns:
        tuple (success: bool, message: str)
    """
    try:
        item = Item.objects.get(slug=slug)
    except Item.DoesNotExist:
        return False, "Product not found."

    if item.stock <= 0:
        return False, f'Product "{item.title}" is out of stock.'

    order, _ = get_or_create_active_order(user)
    order_item, item_created = OrderItem.objects.get_or_create(
        order=order,
        item=item,
    )

    current_qty = order_item.quantity if not item_created else 0
    if current_qty + 1 > item.stock:
        if item_created:
            order_item.delete()
        return False, f'Cannot add more units of "{item.title}". Maximum available stock: {item.stock}.'

    if not item_created:
        order_item.quantity += 1
    else:
        order_item.quantity = 1

    order_item.unit_price = item.price
    order_item.unit_cost = item.cost
    order_item.subtotal = order_item.quantity * order_item.unit_price
    order_item.save()

    if order_item not in order.items.all():
        order.items.add(order_item)

    order.calculate_total()
    order.save()
    return True, f'"{item.title}" was added to your cart.'


def remove_single_item_from_cart_service(user: User, slug: str) -> Tuple[bool, str]:
    """
    Decrements 1 unit of an item in the cart, removing it completely if quantity reaches 0.
    """
    order = Order.objects.filter(user=user, status=OrderStatus.PENDING).first()
    if not order:
        return False, "You do not have an active cart."

    order_item = OrderItem.objects.filter(order=order, item__slug=slug).first()
    if not order_item:
        return False, "This product was not in your cart."

    order_item.quantity -= 1
    if order_item.quantity <= 0:
        order.items.remove(order_item)
        order_item.delete()
    else:
        order_item.subtotal = order_item.quantity * order_item.unit_price
        order_item.save()

    order.calculate_total()
    order.save()
    return True, "Item quantity updated."


def remove_item_from_cart_service(user: User, slug: str) -> Tuple[bool, str]:
    """
    Completely removes an item line from the active cart.
    """
    order = Order.objects.filter(user=user, status=OrderStatus.PENDING).first()
    if not order:
        return False, "You do not have an active cart."

    order_item = OrderItem.objects.filter(order=order, item__slug=slug).first()
    if order_item:
        order.items.remove(order_item)
        order_item.delete()

    order.calculate_total()
    order.save()
    return True, "Product removed from cart."


def apply_discount_service(user: User, code: str) -> Tuple[bool, str]:
    """
    Applies discount coupon to active cart.
    """
    order = Order.objects.filter(user=user, status=OrderStatus.PENDING).first()
    if not order:
        return False, "You do not have an active cart."

    clean_code = (code or '').strip().upper()
    if clean_code in ['DESC10', 'PROMO10']:
        order.discount_code = clean_code
        order.calculate_total()
        order.save()
        return True, f'Promo code "{clean_code}" applied! 10% discount subtracted.'
    elif clean_code in ['OFF500', 'DESCUENTO']:
        order.discount_code = clean_code
        order.calculate_total()
        order.save()
        return True, f'Promo code "{clean_code}" applied! $500.00 discount subtracted.'
    else:
        return False, 'Invalid discount code. Try DESC10 or OFF500.'


def process_checkout_service(user: User, payment_method: str = PaymentMethod.CREDIT_CARD) -> Tuple[bool, str]:
    """
    Processes final checkout for active cart: adjusts inventory, records prices and marks as PAID.
    """
    order = Order.objects.filter(user=user, status=OrderStatus.PENDING).first()
    if not order or not order.items.exists():
        return False, "Your cart is empty."

    order.payment_method = payment_method
    order.shipping_cost = order.recalculate_shipping_cost()
    order.status = OrderStatus.PAID
    order.ordered_date = timezone.now()

    for order_item in order.items.all():
        order_item.unit_price = order_item.item.price
        order_item.unit_cost = order_item.item.cost
        order_item.subtotal = order_item.quantity * order_item.unit_price
        order_item.save()

        if order_item.item.stock > 0:
            order_item.item.stock = max(0, order_item.item.stock - order_item.quantity)
            order_item.item.save(update_fields=['stock'])

    order.calculate_total()
    order.save()
    return True, "Your purchase was completed successfully!"
