"""
apps/orders/customer_insights_service.py

CRM and Customer Lifetime Value (LTV) insights, RFM behavioral segmentation,
and geographic revenue distribution.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List
from django.db.models import Sum, Count, Max, Min, Avg, F
from django.utils import timezone

from apps.orders.models import Order, Profile, OrderStatus


def get_customer_insights_service(limit: int = 20) -> Dict[str, Any]:
    """
    Computes RFM customer segment distribution, Average LTV, repeat buyer rates,
    and geographic sales density.

    Args:
        limit (int): Max top customers to return (clamped between 1 and 100).

    Returns:
        dict: {
            summary: {total_customers, repeat_customer_rate_pct, avg_customer_ltv, segment_counts},
            geographic_distribution: {by_country, top_cities},
            top_customers: List[...]
        }
    """
    effective_limit = max(1, min(int(limit), 100))
    now = timezone.now()

    paid_statuses = [OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
    paid_orders = Order.objects.filter(status__in=paid_statuses)

    # Customer aggregates
    customer_qs = (
        paid_orders.values(
            'user_id',
            'user__username',
            'user__email',
            'user__profile__country',
            'user__profile__city',
            'user__profile__province',
        )
        .annotate(
            orders_count=Count('id'),
            total_spend=Sum('total'),
            last_order_date=Max('ordered_date'),
            first_order_date=Min('ordered_date'),
        )
        .order_by('-total_spend')
    )

    total_customers = customer_qs.count()
    if total_customers == 0:
        return {
            'summary': {
                'total_customers': 0,
                'repeat_customer_rate_pct': 0.0,
                'avg_customer_ltv': 0.0,
                'segment_counts': {
                    'champions_vip': 0,
                    'loyal_customers': 0,
                    'new_customers': 0,
                    'at_risk': 0,
                    'one_time_buyers': 0,
                }
            },
            'geographic_distribution': {
                'by_country': [],
                'top_cities': [],
            },
            'top_customers': [],
        }

    segment_counts = {
        'champions_vip': 0,
        'loyal_customers': 0,
        'new_customers': 0,
        'at_risk': 0,
        'one_time_buyers': 0,
    }

    repeat_customers = 0
    total_spend_all = Decimal('0.00')
    customer_rows: List[Dict[str, Any]] = []

    for c in customer_qs:
        cnt = int(c['orders_count'] or 0)
        spend = Decimal(str(c['total_spend'] or 0.0))
        total_spend_all += spend

        if cnt > 1:
            repeat_customers += 1

        last_date = c['last_order_date']
        first_date = c['first_order_date']

        days_since_last = (now - last_date).days if last_date else 999
        days_since_first = (now - first_date).days if first_date else 999

        # RFM Segment Assignment
        if cnt >= 3 and spend >= Decimal('1000.00'):
            seg = 'Champions / VIP'
            segment_counts['champions_vip'] += 1
        elif cnt >= 2:
            seg = 'Loyal Customer'
            segment_counts['loyal_customers'] += 1
        elif days_since_first <= 30 and cnt == 1:
            seg = 'New Customer'
            segment_counts['new_customers'] += 1
        elif days_since_last > 60:
            seg = 'At Risk'
            segment_counts['at_risk'] += 1
        else:
            seg = 'One-Time Buyer'
            segment_counts['one_time_buyers'] += 1

        customer_rows.append({
            'user_id': c['user_id'],
            'username': c['user__username'],
            'email': c['user__email'],
            'country': c['user__profile__country'] or 'United States',
            'city': c['user__profile__city'] or 'Unknown',
            'orders_count': cnt,
            'total_spend': float(round(spend, 2)),
            'last_order_date': last_date.strftime('%Y-%m-%d %H:%M') if last_date else None,
            'days_since_last_order': days_since_last,
            'segment': seg,
        })

    repeat_rate = float(round((repeat_customers / total_customers) * 100, 2))
    avg_ltv = float(round(total_spend_all / total_customers, 2))

    # Geographic breakdown by country
    country_qs = (
        paid_orders.values(
            country_name=F('user__profile__country')
        )
        .annotate(
            orders_count=Count('id'),
            total_revenue=Sum('total'),
            unique_customers=Count('user_id', distinct=True),
        )
        .order_by('-total_revenue')
    )

    by_country: List[Dict[str, Any]] = []
    for row in country_qs:
        by_country.append({
            'country': row['country_name'] or 'United States',
            'orders_count': row['orders_count'],
            'total_revenue': float(round(row['total_revenue'] or 0.0, 2)),
            'unique_customers': row['unique_customers'],
        })

    # Geographic breakdown by city
    city_qs = (
        paid_orders.exclude(user__profile__city__isnull=True)
        .exclude(user__profile__city__exact='')
        .values(
            city_name=F('user__profile__city'),
            country_name=F('user__profile__country'),
        )
        .annotate(
            orders_count=Count('id'),
            total_revenue=Sum('total'),
        )
        .order_by('-total_revenue')[:10]
    )

    top_cities: List[Dict[str, Any]] = []
    for row in city_qs:
        top_cities.append({
            'city': row['city_name'],
            'country': row['country_name'] or 'United States',
            'orders_count': row['orders_count'],
            'total_revenue': float(round(row['total_revenue'] or 0.0, 2)),
        })

    return {
        'summary': {
            'total_customers': total_customers,
            'repeat_customer_rate_pct': repeat_rate,
            'avg_customer_ltv': avg_ltv,
            'segment_counts': segment_counts,
        },
        'geographic_distribution': {
            'by_country': by_country,
            'top_cities': top_cities,
        },
        'top_customers': customer_rows[:effective_limit],
    }
