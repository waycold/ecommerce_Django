"""
apps/orders/services.py

Business logic and domain service layer for cart operations,
order calculations, discount codes, and checkout processing.
"""

import random
import time
from decimal import Decimal
from typing import Optional, Tuple
from django.contrib.auth.models import User
from django.db import transaction
from django.db.utils import OperationalError
from django.utils import timezone
from apps.orders.models import Order, OrderItem, OrderStatus, PaymentMethod
from apps.catalog.models import Item
from apps.orders.customer_insights_service import get_customer_insights_service


class InsufficientStockError(Exception):
    """Raised inside the checkout transaction to force a rollback when a locked
    Item does not have enough stock for the requested quantity."""
    pass


# Retry budget for transient lock-contention errors from the database while
# acquiring the stock lock (e.g. two checkouts racing for the same Item).
# The delay carries random jitter so that two checkouts released by the same
# trigger (e.g. a load balancer fan-out, or two threads woken at the same
# instant) don't stay locked in step, retrying and colliding on every attempt
# in unison until both exhaust their budget.
_LOCK_CONTENTION_MAX_RETRIES = 8
_LOCK_CONTENTION_RETRY_DELAY_SECONDS = 0.05
_LOCK_CONTENTION_RETRY_JITTER_SECONDS = 0.05



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

    Runs entirely inside one transaction. Every Item involved is locked with
    select_for_update() -- in ascending pk order, so that two checkouts sharing more
    than one item always request their locks in the same order and cannot deadlock
    against each other -- and stock is revalidated after the lock is acquired. If any
    item no longer has enough stock, the whole checkout is rolled back and rejected;
    stock is never silently clamped to 0.

    The order lookup and the empty-cart check are re-read on every retry attempt,
    inside the same try/except that guards the locked transaction below: under
    real contention (e.g. another checkout mid-commit against the same tables)
    those plain reads can themselves raise OperationalError, and they must be
    retried too instead of escaping uncaught.
    """
    for attempt in range(_LOCK_CONTENTION_MAX_RETRIES):
        try:
            order = Order.objects.filter(user=user, status=OrderStatus.PENDING).first()
            if not order or not order.items.exists():
                return False, "Your cart is empty."

            with transaction.atomic():
                _run_checkout_transaction(order, payment_method)
            return True, "Your purchase was completed successfully!"
        except InsufficientStockError as exc:
            return False, str(exc)
        except OperationalError:
            # The database could not grant the lock this checkout needed right now
            # (e.g. another order is mid-checkout for the same item). Back off
            # briefly and retry so the loser of the race gets a chance to re-read
            # the freshly committed stock, instead of surfacing a raw DB error.
            if attempt == _LOCK_CONTENTION_MAX_RETRIES - 1:
                return False, (
                    "Insufficient stock: this item is currently being purchased in "
                    "another order. Please try again."
                )
            delay = _LOCK_CONTENTION_RETRY_DELAY_SECONDS + random.uniform(
                0, _LOCK_CONTENTION_RETRY_JITTER_SECONDS
            )
            time.sleep(delay)


def _run_checkout_transaction(order: Order, payment_method: str) -> None:
    """
    Must run inside transaction.atomic(). Locks every Item in the order (ascending
    pk order, to keep lock acquisition order consistent across concurrent
    checkouts and avoid deadlocking against them), revalidates stock, and either
    raises InsufficientStockError (rolling back) or commits the paid order.
    """
    order_items = list(order.items.select_related('item').all())
    item_ids = sorted({order_item.item_id for order_item in order_items})
    locked_items = {
        item.pk: item
        for item in Item.objects.select_for_update().filter(pk__in=item_ids).order_by('pk')
    }

    for order_item in order_items:
        item = locked_items[order_item.item_id]
        if item.stock < order_item.quantity:
            raise InsufficientStockError(
                f'Insufficient stock for "{item.title}": '
                f'only {item.stock} unit(s) available, {order_item.quantity} requested.'
            )

    order.payment_method = payment_method
    order.shipping_cost = order.recalculate_shipping_cost()
    order.status = OrderStatus.PAID
    order.ordered_date = timezone.now()

    for order_item in order_items:
        item = locked_items[order_item.item_id]
        order_item.unit_price = item.price
        order_item.unit_cost = item.cost
        order_item.subtotal = order_item.quantity * order_item.unit_price
        order_item.save()

        item.stock -= order_item.quantity
        item.save(update_fields=['stock'])

    order.calculate_total()
    order.save()
