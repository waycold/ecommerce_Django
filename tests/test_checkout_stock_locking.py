"""
tests/test_checkout_stock_locking.py

Verifies apps.orders.services.process_checkout_service:
- decrements stock and marks the order PAID inside a single transaction,
- revalidates stock >= quantity for every locked Item and rejects the whole
  checkout with an explicit error instead of silently clamping to 0,
- and, under two genuinely concurrent checkouts racing for the last unit of
  the same Item, lets exactly one succeed while the other is cleanly
  rejected -- never both PAID, never both rejected.
"""
import threading

import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from django.db import connections

from apps.catalog.models import Item
from apps.orders.models import Order, OrderItem, OrderStatus
from apps.orders.services import process_checkout_service


def _make_item(stock, title="Contested Item"):
    return Item.objects.create(
        title=title,
        description="Item used to exercise checkout stock locking.",
        price=Decimal("100.00"),
        cost=Decimal("50.00"),
        stock=stock,
        is_active=True,
    )


def _make_cart(user, item, quantity=1):
    order = Order.objects.create(user=user, status=OrderStatus.PENDING)
    OrderItem.objects.create(
        order=order,
        item=item,
        quantity=quantity,
        unit_price=item.price,
        unit_cost=item.cost,
    )
    return order


@pytest.mark.django_db
def test_checkout_succeeds_and_decrements_stock():
    user = User.objects.create_user(username="buyer1", password="pw")
    item = _make_item(stock=5)
    _make_cart(user, item, quantity=2)

    success, message = process_checkout_service(user)

    assert success is True
    item.refresh_from_db()
    assert item.stock == 3


@pytest.mark.django_db
def test_checkout_rejects_insufficient_stock_without_clamping_to_zero():
    user = User.objects.create_user(username="buyer2", password="pw")
    item = _make_item(stock=1)
    order = _make_cart(user, item, quantity=5)

    success, message = process_checkout_service(user)

    assert success is False
    assert "Insufficient stock" in message
    assert item.title in message

    item.refresh_from_db()
    assert item.stock == 1  # untouched -- never clamped to 0

    order.refresh_from_db()
    assert order.status == OrderStatus.PENDING  # rolled back, never marked PAID


@pytest.mark.django_db
def test_multi_item_checkout_rolls_back_fully_when_one_item_lacks_stock():
    """
    An order with two items where only one lacks stock must reject the whole
    checkout -- the item that DID have enough stock must not be decremented
    either, proving the transaction is all-or-nothing.
    """
    user = User.objects.create_user(username="buyer3", password="pw")
    plenty_item = _make_item(stock=10, title="Plenty Item")
    scarce_item = _make_item(stock=0, title="Scarce Item")
    order = Order.objects.create(user=user, status=OrderStatus.PENDING)
    OrderItem.objects.create(order=order, item=plenty_item, quantity=1,
                              unit_price=plenty_item.price, unit_cost=plenty_item.cost)
    OrderItem.objects.create(order=order, item=scarce_item, quantity=1,
                              unit_price=scarce_item.price, unit_cost=scarce_item.cost)

    success, message = process_checkout_service(user)

    assert success is False
    assert "Scarce Item" in message

    plenty_item.refresh_from_db()
    scarce_item.refresh_from_db()
    assert plenty_item.stock == 10  # not decremented despite having enough
    assert scarce_item.stock == 0

    order.refresh_from_db()
    assert order.status == OrderStatus.PENDING


@pytest.mark.django_db
def test_second_sequential_checkout_on_same_last_unit_is_rejected():
    """
    Without concurrency: two different users each try to buy the single
    remaining unit of the same item. The first checkout must succeed and the
    second must be explicitly rejected -- never silently marked PAID against
    an item that has no stock left.
    """
    item = _make_item(stock=1)
    buyer_a = User.objects.create_user(username="seq_buyer_a", password="pw")
    buyer_b = User.objects.create_user(username="seq_buyer_b", password="pw")
    _make_cart(buyer_a, item, quantity=1)
    order_b = _make_cart(buyer_b, item, quantity=1)

    success_a, _ = process_checkout_service(buyer_a)
    success_b, message_b = process_checkout_service(buyer_b)

    assert success_a is True
    assert success_b is False
    assert "Insufficient stock" in message_b

    item.refresh_from_db()
    assert item.stock == 0

    order_b.refresh_from_db()
    assert order_b.status == OrderStatus.PENDING


@pytest.mark.django_db(transaction=True)
def test_concurrent_checkouts_on_last_unit_never_both_succeed():
    """
    Fires two real, independently-connected checkouts (separate threads, each
    opening its own DB connection) against an item with stock=1. A
    threading.Barrier forces both threads into process_checkout_service at
    essentially the same instant, so the race is genuine rather than
    timing-dependent -- there is no sleep anywhere in this test.

    Note on SQLite vs. Postgres: SQLite has no real row-level locking, so
    select_for_update() is a no-op at the storage layer here (it is real
    row-level locking on Postgres in production). What SQLite *does* give us
    is that concurrent writers to the same file are serialized by the engine
    itself: whichever checkout's write reaches the database first commits,
    and the loser's write is blocked until that commit completes. Because our
    service revalidates stock against the freshly re-read, lock-acquired Item
    row before deciding to write (rather than trusting an earlier read), the
    loser observes the already-decremented stock and is rejected cleanly --
    the same observable guarantee select_for_update() provides on Postgres.

    Acceptance: exactly one checkout succeeds, the other fails with an
    explicit "insufficient stock" error. Never both succeed, never both fail.
    """
    item = _make_item(stock=1)
    buyer_a = User.objects.create_user(username="race_buyer_a", password="pw")
    buyer_b = User.objects.create_user(username="race_buyer_b", password="pw")
    order_a = _make_cart(buyer_a, item, quantity=1)
    order_b = _make_cart(buyer_b, item, quantity=1)

    barrier = threading.Barrier(2)
    results = {}

    def run_checkout(user_id, key):
        try:
            barrier.wait(timeout=5)
            user = User.objects.get(pk=user_id)
            results[key] = process_checkout_service(user)
        except Exception as exc:  # capture instead of swallowing: a leaked
            # exception (e.g. a raw database lock error) must fail the test
            # loudly, not be mistaken for a clean rejection.
            results[key] = ("EXCEPTION", repr(exc))
        finally:
            connections.close_all()

    thread_a = threading.Thread(target=run_checkout, args=(buyer_a.pk, "a"))
    thread_b = threading.Thread(target=run_checkout, args=(buyer_b.pk, "b"))

    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=15)
    thread_b.join(timeout=15)

    assert not thread_a.is_alive() and not thread_b.is_alive(), "checkout threads did not finish in time"
    assert set(results.keys()) == {"a", "b"}, f"a thread crashed before recording a result: {results}"

    outcomes = [results["a"], results["b"]]
    successes = [o for o in outcomes if o[0] is True]
    failures = [o for o in outcomes if o[0] is False]

    assert len(successes) == 1, f"expected exactly one successful checkout, got: {outcomes}"
    assert len(failures) == 1, f"expected exactly one explicitly rejected checkout, got: {outcomes}"
    assert "Insufficient stock" in failures[0][1]

    item.refresh_from_db()
    assert item.stock == 0

    order_a.refresh_from_db()
    order_b.refresh_from_db()
    statuses = {order_a.status, order_b.status}
    assert statuses == {OrderStatus.PAID, OrderStatus.PENDING}
