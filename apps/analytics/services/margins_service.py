"""
apps/analytics/services/margins_service.py

Gross margin and profitability analytics service.
Calculates revenue, cost, profit, and margin % aggregated by product, category, brand, or supplier.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List, Union
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.utils.dateparse import parse_date

from apps.orders.models import OrderItem, OrderStatus


VALID_DIMENSIONS = {'product', 'category', 'brand', 'supplier'}
VALID_ORDER_BYS = {'margin_desc', 'margin_asc', 'revenue_desc', 'profit_desc'}


def calculate_margins_service(
    dimension: str = "product",
    order_by: str = "margin_desc",
    date_from: Optional[Union[str, date, datetime]] = None,
    date_to: Optional[Union[str, date, datetime]] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Computes margin percentages and gross profit grouped by dimension.

    Args:
        dimension (str): 'product' | 'category' | 'brand' | 'supplier'
        order_by (str): 'margin_desc' | 'margin_asc' | 'revenue_desc' | 'profit_desc'
        date_from (str, optional): ISO date string 'YYYY-MM-DD' or date/datetime object
        date_to (str, optional): ISO date string 'YYYY-MM-DD' or date/datetime object
        limit (int): Max rows to return (clamped between 1 and 100).

    Returns:
        dict: {dimension, order_by, limit, date_from, date_to, overall_margin, results}
    """
    effective_limit = max(1, min(int(limit), 100))
    dim_clean = str(dimension or "product").lower().strip()
    if dim_clean not in VALID_DIMENSIONS:
        dim_clean = "product"

    order_clean = str(order_by or "margin_desc").lower().strip()
    if order_clean not in VALID_ORDER_BYS:
        order_clean = "margin_desc"

    paid_statuses = [OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
    queryset = OrderItem.objects.filter(order__status__in=paid_statuses)

    if date_from:
        if isinstance(date_from, (datetime, date)):
            parsed_from = date_from.date() if isinstance(date_from, datetime) else date_from
        else:
            parsed_from = parse_date(str(date_from).strip())
        if parsed_from:
            queryset = queryset.filter(order__ordered_date__date__gte=parsed_from)

    if date_to:
        if isinstance(date_to, (datetime, date)):
            parsed_to = date_to.date() if isinstance(date_to, datetime) else date_to
        else:
            parsed_to = parse_date(str(date_to).strip())
        if parsed_to:
            queryset = queryset.filter(order__ordered_date__date__lte=parsed_to)

    cost_expr = ExpressionWrapper(
        F('unit_cost') * F('quantity'),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )
    profit_expr = ExpressionWrapper(
        F('subtotal') - (F('unit_cost') * F('quantity')),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    if dim_clean == 'product':
        grouped_qs = queryset.values(
            'item_id',
            'item__title',
            'item__category__name',
            'item__brand__name'
        ).annotate(
            total_revenue=Sum('subtotal'),
            total_cost=Sum(cost_expr),
            gross_profit=Sum(profit_expr),
            units_sold=Sum('quantity'),
        )
    elif dim_clean == 'category':
        grouped_qs = queryset.values(
            category_name=Coalesce('item__category__name', F('item__category__name'))
        ).annotate(
            total_revenue=Sum('subtotal'),
            total_cost=Sum(cost_expr),
            gross_profit=Sum(profit_expr),
            units_sold=Sum('quantity'),
        )
    elif dim_clean == 'brand':
        grouped_qs = queryset.values(
            brand_name=Coalesce('item__brand__name', F('item__brand__name'))
        ).annotate(
            total_revenue=Sum('subtotal'),
            total_cost=Sum(cost_expr),
            gross_profit=Sum(profit_expr),
            units_sold=Sum('quantity'),
        )
    elif dim_clean == 'supplier':
        grouped_qs = queryset.values(
            supplier_name=Coalesce('item__supplier__name', F('item__supplier__name'))
        ).annotate(
            total_revenue=Sum('subtotal'),
            total_cost=Sum(cost_expr),
            gross_profit=Sum(profit_expr),
            units_sold=Sum('quantity'),
        )

    # Convert to list and compute margin % for in-memory / database sorting
    results_list: List[Dict[str, Any]] = []
    total_rev_all = Decimal('0.00')
    total_cost_all = Decimal('0.00')
    total_profit_all = Decimal('0.00')

    for row in grouped_qs:
        rev = Decimal(str(row['total_revenue'] or 0.0))
        cost = Decimal(str(row['total_cost'] or 0.0))
        profit = Decimal(str(row['gross_profit'] or 0.0))
        units = int(row['units_sold'] or 0)
        margin_pct = float(round((profit / rev) * 100, 2)) if rev > 0 else 0.0

        total_rev_all += rev
        total_cost_all += cost
        total_profit_all += profit

        item_dict = {
            'revenue': float(round(rev, 2)),
            'cost': float(round(cost, 2)),
            'gross_profit': float(round(profit, 2)),
            'gross_margin_pct': margin_pct,
            'units_sold': units,
        }

        if dim_clean == 'product':
            item_dict['item_id'] = row['item_id']
            item_dict['title'] = row['item__title']
            item_dict['category'] = row['item__category__name'] or 'Uncategorized'
            item_dict['brand'] = row['item__brand__name'] or 'Generic'
        elif dim_clean == 'category':
            item_dict['category'] = row['category_name'] or 'Uncategorized'
        elif dim_clean == 'brand':
            item_dict['brand'] = row['brand_name'] or 'Generic'
        elif dim_clean == 'supplier':
            item_dict['supplier'] = row['supplier_name'] or 'Unknown'

        results_list.append(item_dict)

    # Sort results
    if order_clean == 'margin_desc':
        results_list.sort(key=lambda x: x['gross_margin_pct'], reverse=True)
    elif order_clean == 'margin_asc':
        results_list.sort(key=lambda x: x['gross_margin_pct'])
    elif order_clean == 'revenue_desc':
        results_list.sort(key=lambda x: x['revenue'], reverse=True)
    elif order_clean == 'profit_desc':
        results_list.sort(key=lambda x: x['gross_profit'], reverse=True)

    overall_margin_pct = float(round((total_profit_all / total_rev_all) * 100, 2)) if total_rev_all > 0 else 0.0

    return {
        'dimension': dim_clean,
        'order_by': order_clean,
        'date_from': date_from,
        'date_to': date_to,
        'limit': effective_limit,
        'overall_margin': {
            'total_revenue': float(round(total_rev_all, 2)),
            'total_cost': float(round(total_cost_all, 2)),
            'total_gross_profit': float(round(total_profit_all, 2)),
            'overall_margin_pct': overall_margin_pct,
        },
        'results': results_list[:effective_limit],
    }
