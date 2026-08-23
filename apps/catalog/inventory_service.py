"""
apps/catalog/inventory_service.py

Inventory health, stockout risk forecasting, valuation, and critical item runout metrics.
"""

from datetime import timedelta
from decimal import Decimal
from typing import Dict, Any, List
from django.db.models import Sum, F, Q
from django.utils import timezone

from apps.catalog.models import Item
from apps.orders.models import OrderItem, OrderStatus


def get_inventory_health_service(limit: int = 20) -> Dict[str, Any]:
    """
    Computes stock metrics, stockout risks, catalog valuation, and critical items runout velocity.

    Args:
        limit (int): Max number of critical items to return (clamped between 1 and 100).

    Returns:
        dict: {
            metrics: {total_active_skus, out_of_stock_count, low_stock_count, healthy_stock_count, stockout_rate_pct},
            inventory_valuation: {total_cost_value, total_retail_value, projected_profit_potential, potential_margin_pct},
            critical_items: List[...]
        }
    """
    effective_limit = max(1, min(int(limit), 100))

    active_items_qs = Item.objects.filter(is_active=True).select_related('category', 'brand')
    total_active_skus = active_items_qs.count()

    out_of_stock_count = active_items_qs.filter(stock=0).count()
    low_stock_count = active_items_qs.filter(stock__gt=0, stock__lte=F('minimum_stock')).count()
    healthy_stock_count = max(0, total_active_skus - out_of_stock_count - low_stock_count)
    stockout_rate_pct = float(round((out_of_stock_count / total_active_skus) * 100, 2)) if total_active_skus > 0 else 0.0

    # Valuation
    valuation_agg = active_items_qs.aggregate(
        total_cost=Sum(F('cost') * F('stock')),
        total_retail=Sum(F('price') * F('stock')),
    )
    total_cost_val = float(round(valuation_agg['total_cost'] or 0.0, 2))
    total_retail_val = float(round(valuation_agg['total_retail'] or 0.0, 2))
    profit_potential = float(round(total_retail_val - total_cost_val, 2))
    potential_margin = float(round((profit_potential / total_retail_val) * 100, 2)) if total_retail_val > 0 else 0.0

    # 30-day velocity calculation
    thirty_days_ago = timezone.now() - timedelta(days=30)
    paid_statuses = [OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
    sales_30d_qs = (
        OrderItem.objects.filter(
            order__status__in=paid_statuses,
            order__ordered_date__gte=thirty_days_ago
        )
        .values('item_id')
        .annotate(units_sold=Sum('quantity'))
    )
    sales_30d_dict = {s['item_id']: int(s['units_sold'] or 0) for s in sales_30d_qs}

    # Fetch critical and low stock items
    critical_qs = active_items_qs.filter(
        Q(stock=0) | Q(stock__lte=F('minimum_stock'))
    ).order_by('stock')

    critical_items_list: List[Dict[str, Any]] = []
    for itm in critical_qs:
        units_30d = sales_30d_dict.get(itm.id, 0)
        daily_velocity = round(units_30d / 30.0, 2)
        
        if itm.stock == 0:
            status_label = "OUT_OF_STOCK"
            days_to_stockout = 0.0
        elif daily_velocity > 0:
            days_to_stockout = round(itm.stock / daily_velocity, 1)
            status_label = "CRITICAL" if itm.stock <= itm.minimum_stock else "LOW"
        else:
            days_to_stockout = 999.0
            status_label = "CRITICAL" if itm.stock <= itm.minimum_stock else "LOW"

        critical_items_list.append({
            'id': itm.id,
            'title': itm.title,
            'category': itm.category.name if itm.category else 'Uncategorized',
            'brand': itm.brand.name if itm.brand else 'Generic',
            'stock': itm.stock,
            'minimum_stock': itm.minimum_stock,
            'price': float(itm.price),
            'cost': float(itm.cost),
            'units_sold_last_30d': units_30d,
            'daily_sales_velocity': daily_velocity,
            'estimated_days_to_stockout': days_to_stockout,
            'stock_status': status_label,
        })

    # Sort critical items: Out of stock first, then lowest days to stockout
    critical_items_list.sort(key=lambda x: (0 if x['stock'] == 0 else 1, x['estimated_days_to_stockout'], x['stock']))

    return {
        'metrics': {
            'total_active_skus': total_active_skus,
            'out_of_stock_count': out_of_stock_count,
            'low_stock_count': low_stock_count,
            'healthy_stock_count': healthy_stock_count,
            'stockout_rate_pct': stockout_rate_pct,
        },
        'inventory_valuation': {
            'total_cost_value': total_cost_val,
            'total_retail_value': total_retail_val,
            'projected_profit_potential': profit_potential,
            'potential_margin_pct': potential_margin,
        },
        'critical_items': critical_items_list[:effective_limit],
    }
