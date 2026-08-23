"""
apps/analytics/services/query_engine_service.py

Dynamic multidimensional sales query and aggregation engine.
Allows slicing and dicing sales metrics across temporal (day, week, month, quarter)
and catalog/customer dimensions (category, brand, supplier, payment_method, country).
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from django.db.models import Sum, Count, F, Q, Value, DecimalField, ExpressionWrapper
from django.db.models.functions import (
    TruncDate,
    TruncWeek,
    TruncMonth,
    TruncQuarter,
    Coalesce,
    Round,
)
from django.utils.dateparse import parse_date

from apps.orders.models import OrderItem, Order, OrderStatus


VALID_GROUP_BY_DIMENSIONS = {
    'day',
    'week',
    'month',
    'quarter',
    'category',
    'brand',
    'supplier',
    'payment_method',
    'country',
}


def dynamic_sales_query_service(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    group_by: str = "category",
    metrics: str = "revenue,orders,units",
    status: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Executes dynamic database aggregations across dimensions and date windows.

    Args:
        date_from (str, optional): ISO date string 'YYYY-MM-DD'
        date_to (str, optional): ISO date string 'YYYY-MM-DD'
        group_by (str): Dimension to group by ('day'|'week'|'month'|'quarter'|'category'|'brand'|'supplier'|'payment_method'|'country')
        metrics (str): Comma-separated list of metrics to include
        status (str, optional): Order status filter. Defaults to completed paid orders if omitted.
        limit (int): Max rows returned (clamped between 1 and 100).

    Returns:
        dict: {query_metadata, summary, data}
    """
    effective_limit = max(1, min(int(limit), 100))
    cleaned_group_by = str(group_by or "category").lower().strip()
    if cleaned_group_by not in VALID_GROUP_BY_DIMENSIONS:
        cleaned_group_by = "category"

    # Base queryset
    queryset = OrderItem.objects.all()

    # Status filter
    if status:
        status_clean = str(status).upper().strip()
        queryset = queryset.filter(order__status=status_clean)
    else:
        paid_statuses = [OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
        queryset = queryset.filter(order__status__in=paid_statuses)

    # Date range filters
    if date_from:
        parsed_from = parse_date(str(date_from).strip())
        if parsed_from:
            queryset = queryset.filter(order__ordered_date__date__gte=parsed_from)

    if date_to:
        parsed_to = parse_date(str(date_to).strip())
        if parsed_to:
            queryset = queryset.filter(order__ordered_date__date__lte=parsed_to)

    # Grouping Annotation
    if cleaned_group_by == 'day':
        grouped_qs = queryset.annotate(group_key=TruncDate('order__ordered_date'))
        order_field = '-group_key'
    elif cleaned_group_by == 'week':
        grouped_qs = queryset.annotate(group_key=TruncWeek('order__ordered_date'))
        order_field = '-group_key'
    elif cleaned_group_by == 'month':
        grouped_qs = queryset.annotate(group_key=TruncMonth('order__ordered_date'))
        order_field = '-group_key'
    elif cleaned_group_by == 'quarter':
        grouped_qs = queryset.annotate(group_key=TruncQuarter('order__ordered_date'))
        order_field = '-group_key'
    elif cleaned_group_by == 'category':
        grouped_qs = queryset.annotate(
            group_key=Coalesce('item__category__name', Value('Uncategorized'))
        )
        order_field = '-revenue'
    elif cleaned_group_by == 'brand':
        grouped_qs = queryset.annotate(
            group_key=Coalesce('item__brand__name', Value('Generic'))
        )
        order_field = '-revenue'
    elif cleaned_group_by == 'supplier':
        grouped_qs = queryset.annotate(
            group_key=Coalesce('item__supplier__name', Value('Unknown'))
        )
        order_field = '-revenue'
    elif cleaned_group_by == 'payment_method':
        grouped_qs = queryset.annotate(
            group_key=Coalesce('order__payment_method', Value('CREDIT_CARD'))
        )
        order_field = '-revenue'
    elif cleaned_group_by == 'country':
        grouped_qs = queryset.annotate(
            group_key=Coalesce('order__user__profile__country', Value('United States'))
        )
        order_field = '-revenue'
    else:
        grouped_qs = queryset.annotate(
            group_key=Coalesce('item__category__name', Value('Uncategorized'))
        )
        order_field = '-revenue'

    cost_expr = ExpressionWrapper(
        F('unit_cost') * F('quantity'),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )
    profit_expr = ExpressionWrapper(
        F('subtotal') - (F('unit_cost') * F('quantity')),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    aggregated_data = (
        grouped_qs.values('group_key')
        .annotate(
            revenue=Sum('subtotal'),
            orders_count=Count('order_id', distinct=True),
            units_sold=Sum('quantity'),
            total_cost=Sum(cost_expr),
            gross_profit=Sum(profit_expr),
        )
        .order_by(order_field)
    )

    # Format data list
    data_rows: List[Dict[str, Any]] = []
    total_revenue_acc = Decimal('0.00')
    total_orders_set = set()
    total_units_acc = 0
    total_cost_acc = Decimal('0.00')
    total_profit_acc = Decimal('0.00')

    for row in aggregated_data[:effective_limit]:
        rev = Decimal(str(row['revenue'] or 0.0))
        cost = Decimal(str(row['total_cost'] or 0.0))
        profit = Decimal(str(row['gross_profit'] or 0.0))
        units = int(row['units_sold'] or 0)
        orders = int(row['orders_count'] or 0)
        
        margin_pct = float(round((profit / rev) * 100, 2)) if rev > 0 else 0.0
        avg_basket = float(round(rev / orders, 2)) if orders > 0 else 0.0

        key_val = row['group_key']
        if hasattr(key_val, 'isoformat'):
            dimension_label = key_val.isoformat()
        else:
            dimension_label = str(key_val) if key_val is not None else "Unknown"

        data_rows.append({
            'dimension': dimension_label,
            'revenue': float(round(rev, 2)),
            'orders_count': orders,
            'units_sold': units,
            'total_cost': float(round(cost, 2)),
            'gross_profit': float(round(profit, 2)),
            'gross_margin_pct': margin_pct,
            'avg_order_value': avg_basket,
        })

    # Summary over the whole filtered queryset
    summary_agg = queryset.aggregate(
        total_rev=Sum('subtotal'),
        total_orders=Count('order_id', distinct=True),
        total_units=Sum('quantity'),
        total_cost=Sum(cost_expr),
        total_profit=Sum(profit_expr),
    )

    tot_rev = Decimal(str(summary_agg['total_rev'] or 0.0))
    tot_orders = int(summary_agg['total_orders'] or 0)
    tot_units = int(summary_agg['total_units'] or 0)
    tot_profit = Decimal(str(summary_agg['total_profit'] or 0.0))
    tot_margin = float(round((tot_profit / tot_rev) * 100, 2)) if tot_rev > 0 else 0.0
    tot_aov = float(round(tot_rev / tot_orders, 2)) if tot_orders > 0 else 0.0

    return {
        'query_metadata': {
            'group_by': cleaned_group_by,
            'metrics': metrics,
            'date_from': date_from,
            'date_to': date_to,
            'status': status,
            'limit': effective_limit,
            'total_groups': len(aggregated_data),
        },
        'summary': {
            'total_revenue': float(round(tot_rev, 2)),
            'total_orders': tot_orders,
            'total_units': tot_units,
            'avg_order_value': tot_aov,
            'total_gross_profit': float(round(tot_profit, 2)),
            'avg_gross_margin_pct': tot_margin,
        },
        'data': data_rows,
    }
