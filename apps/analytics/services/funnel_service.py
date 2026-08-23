"""
apps/analytics/services/funnel_service.py

Cart abandonment funnel analysis, promotional coupon ROI & effectiveness,
and payment method conversion metrics.
"""

from datetime import timedelta
from decimal import Decimal
from typing import Dict, Any, List
from django.db.models import Sum, Count, F, Q, Avg
from django.utils import timezone

from apps.orders.models import Order, OrderItem, OrderStatus, PaymentMethod


def calculate_funnel_and_promotions_service(
    period: str = "last_30_days"
) -> Dict[str, Any]:
    """
    Computes conversion funnel, cart abandonment rates, coupon performance, and payment distribution.

    Args:
        period (str): 'last_7_days' | 'last_30_days' | 'last_90_days' | 'last_year' | 'all_time'

    Returns:
        dict: {period, funnel_metrics, abandoned_products_ranking, coupon_effectiveness, payment_methods_breakdown}
    """
    now = timezone.now()
    period_clean = str(period or "last_30_days").lower().strip()

    date_filter = Q()
    if period_clean == 'last_7_days':
        date_filter = Q(start_date__gte=now - timedelta(days=7))
    elif period_clean == 'last_30_days':
        date_filter = Q(start_date__gte=now - timedelta(days=30))
    elif period_clean == 'last_90_days':
        date_filter = Q(start_date__gte=now - timedelta(days=90))
    elif period_clean == 'last_year':
        date_filter = Q(start_date__gte=now - timedelta(days=365))
    else:
        period_clean = 'all_time'

    orders_qs = Order.objects.filter(date_filter)
    total_orders = orders_qs.count()

    paid_statuses = [OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
    completed_orders = orders_qs.filter(status__in=paid_statuses).count()
    pending_orders = orders_qs.filter(status=OrderStatus.PENDING).count()
    canceled_orders = orders_qs.filter(status=OrderStatus.CANCELED).count()

    abandonment_rate = float(round((pending_orders / total_orders) * 100, 2)) if total_orders > 0 else 0.0
    conversion_rate = float(round((completed_orders / total_orders) * 100, 2)) if total_orders > 0 else 0.0
    cancellation_rate = float(round((canceled_orders / total_orders) * 100, 2)) if total_orders > 0 else 0.0

    completed_rev_agg = orders_qs.filter(status__in=paid_statuses).aggregate(
        total_rev=Sum('total'),
        avg_aov=Avg('total'),
    )
    completed_revenue = float(round(completed_rev_agg['total_rev'] or 0.0, 2))
    avg_order_value = float(round(completed_rev_agg['avg_aov'] or 0.0, 2))

    # Abandoned Products Ranking (Items in PENDING orders)
    abandoned_items_qs = (
        OrderItem.objects.filter(
            order__in=orders_qs.filter(status=OrderStatus.PENDING)
        )
        .values('item_id', 'item__title', 'item__category__name', 'item__price')
        .annotate(
            abandoned_carts_count=Count('order_id', distinct=True),
            abandoned_units=Sum('quantity'),
            potential_revenue=Sum('subtotal'),
        )
        .order_by('-abandoned_carts_count', '-potential_revenue')[:10]
    )

    abandoned_products: List[Dict[str, Any]] = []
    for item in abandoned_items_qs:
        abandoned_products.append({
            'item_id': item['item_id'],
            'title': item['item__title'],
            'category': item['item__category__name'] or 'Uncategorized',
            'price': float(item['item__price'] or 0.0),
            'abandoned_carts_count': item['abandoned_carts_count'],
            'abandoned_units': item['abandoned_units'],
            'potential_lost_revenue': float(round(item['potential_revenue'] or 0.0, 2)),
        })

    # Coupon Effectiveness
    coupon_qs = (
        orders_qs.filter(status__in=paid_statuses)
        .exclude(discount_code__isnull=True)
        .exclude(discount_code__exact='')
        .values('discount_code')
        .annotate(
            usage_count=Count('id'),
            total_discount_amount=Sum('discount'),
            total_revenue_generated=Sum('total'),
            avg_order_value=Avg('total'),
        )
        .order_by('-usage_count')
    )

    coupon_stats: List[Dict[str, Any]] = []
    for c in coupon_qs:
        coupon_stats.append({
            'discount_code': c['discount_code'],
            'usage_count': c['usage_count'],
            'total_discount_amount': float(round(c['total_discount_amount'] or 0.0, 2)),
            'total_revenue_generated': float(round(c['total_revenue_generated'] or 0.0, 2)),
            'avg_order_value': float(round(c['avg_order_value'] or 0.0, 2)),
        })

    # Payment Methods Breakdown
    payment_qs = (
        orders_qs.filter(status__in=paid_statuses)
        .values('payment_method')
        .annotate(
            orders_count=Count('id'),
            total_revenue=Sum('total'),
            avg_order_value=Avg('total'),
        )
        .order_by('-total_revenue')
    )

    payment_stats: List[Dict[str, Any]] = []
    for p in payment_qs:
        cnt = p['orders_count']
        rev = float(round(p['total_revenue'] or 0.0, 2))
        pct = float(round((cnt / completed_orders) * 100, 2)) if completed_orders > 0 else 0.0
        payment_stats.append({
            'payment_method': p['payment_method'] or PaymentMethod.CREDIT_CARD,
            'orders_count': cnt,
            'total_revenue': rev,
            'avg_order_value': float(round(p['avg_order_value'] or 0.0, 2)),
            'percentage_of_total_orders': pct,
        })

    return {
        'period': period_clean,
        'funnel_metrics': {
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'pending_orders': pending_orders,
            'canceled_orders': canceled_orders,
            'cart_abandonment_rate_pct': abandonment_rate,
            'conversion_rate_pct': conversion_rate,
            'cancellation_rate_pct': cancellation_rate,
            'completed_revenue': completed_revenue,
            'avg_order_value': avg_order_value,
        },
        'abandoned_products_ranking': abandoned_products,
        'coupon_effectiveness': coupon_stats,
        'payment_methods_breakdown': payment_stats,
    }
