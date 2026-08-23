"""
apps/analytics/services/kpi_service.py

Real-time KPI calculations and formatted metrics for Managerial Dashboard and AI API contracts.
"""

from django.db.models import Sum
from django.utils import timezone
from apps.orders.models import Order, OrderItem, OrderStatus


def get_dashboard_kpis() -> dict:
    """
    Calculates key performance indicators (KPIs) in real-time for the Managerial Dashboard.
    """
    now = timezone.now()
    current_year = now.year
    current_month = now.month

    paid_statuses = [OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED]

    monthly_revenue_agg = Order.objects.filter(
        status__in=paid_statuses,
        ordered_date__year=current_year,
        ordered_date__month=current_month
    ).aggregate(
        total_revenue=Sum('total')
    )
    monthly_revenue = monthly_revenue_agg['total_revenue'] or 0.0

    monthly_orders_count = Order.objects.filter(
        status__in=paid_statuses,
        ordered_date__year=current_year,
        ordered_date__month=current_month
    ).count()

    avg_order_value = float(monthly_revenue) / float(monthly_orders_count) if monthly_orders_count > 0 else 0.0

    active_customers_count = Order.objects.filter(
        status__in=paid_statuses,
        ordered_date__year=current_year,
        ordered_date__month=current_month
    ).values('user').distinct().count()

    abandoned_carts_count = Order.objects.filter(
        status=OrderStatus.PENDING
    ).count()

    top_products_qs = OrderItem.objects.filter(
        order__status__in=paid_statuses
    ).values(
        'item__id',
        'item__title',
        'item__category__name',
        'item__price'
    ).annotate(
        total_units_sold=Sum('quantity'),
        total_revenue_generated=Sum('subtotal')
    ).order_by('-total_units_sold')[:8]

    top_products = list(top_products_qs)

    return {
        'current_month_name': now.strftime('%B %Y'),
        'monthly_revenue': float(monthly_revenue),
        'monthly_orders_count': monthly_orders_count,
        'avg_order_value': round(avg_order_value, 2),
        'active_customers_count': active_customers_count,
        'abandoned_carts_count': abandoned_carts_count,
        'top_products': top_products,
        'top_product_star': top_products[0] if top_products else None,
    }


def _format_top_products(top_products_raw: list) -> list:
    formatted = []
    for p in top_products_raw:
        formatted.append({
            'product_id': p.get('item__id'),
            'title': p.get('item__title'),
            'category': p.get('item__category__name'),
            'price': float(p.get('item__price') or 0.0),
            'total_units_sold': int(p.get('total_units_sold') or 0),
            'total_revenue_generated': float(p.get('total_revenue_generated') or 0.0),
        })
    return formatted


def _format_top_product_star(star_raw: dict) -> dict:
    if not star_raw:
        return None
    return {
        'product_id': star_raw.get('item__id'),
        'title': star_raw.get('item__title'),
        'category': star_raw.get('item__category__name'),
        'price': float(star_raw.get('item__price') or 0.0),
        'total_units_sold': int(star_raw.get('total_units_sold') or 0),
        'total_revenue_generated': float(star_raw.get('total_revenue_generated') or 0.0),
    }


def get_internal_metrics_service(metric_type: str = 'overview') -> tuple:
    """
    Internal business metrics service for AI orchestrator consumption.
    """
    from apps.analytics.services.forecast_service import get_forecast_data

    cleaned_type = (metric_type or 'overview').lower().strip()

    valid_types = {
        'overview', 'kpis', 'forecast', 'sales_trend',
        'category_distribution', 'top_products', 'all'
    }

    if cleaned_type not in valid_types:
        return {
            'error': 'Bad Request',
            'detail': 'Invalid metric_type. Supported values: overview, kpis, forecast, sales_trend, category_distribution, top_products, all',
        }, 400

    if cleaned_type in ('overview', 'kpis'):
        kpis = get_dashboard_kpis()
        payload = {
            'metric_type': cleaned_type,
            'current_month': kpis['current_month_name'],
            'monthly_revenue': float(kpis['monthly_revenue']),
            'monthly_orders': int(kpis['monthly_orders_count']),
            'avg_order_value': float(kpis['avg_order_value']),
            'active_customers': int(kpis['active_customers_count']),
            'abandoned_carts': int(kpis['abandoned_carts_count']),
            'top_product_star': _format_top_product_star(kpis['top_product_star']),
        }
        return payload, 200

    elif cleaned_type in ('forecast', 'sales_trend'):
        forecast_data = get_forecast_data()
        payload = {
            'metric_type': cleaned_type,
            'historical_trend': {
                'months': forecast_data['months_labels'],
                'revenue': [float(r) for r in forecast_data['historical_revenue']],
            },
            'forecast_3_months': {
                'months': forecast_data['forecast_months'],
                'projected_revenue': [float(r) for r in forecast_data['forecast_revenue']],
                'upper_bound': [float(r) for r in forecast_data['forecast_upper']],
                'lower_bound': [float(r) for r in forecast_data['forecast_lower']],
            },
            'next_month_projected': float(forecast_data['next_month_projected']),
            'mom_growth_pct': float(forecast_data['mom_growth']),
            'seasonality_index': float(forecast_data['seasonality_index']),
        }
        return payload, 200

    elif cleaned_type == 'category_distribution':
        forecast_data = get_forecast_data()
        categories_data = [
            {'category': label, 'revenue': float(rev)}
            for label, rev in zip(forecast_data['category_labels'], forecast_data['category_revenues'])
        ]
        payload = {
            'metric_type': 'category_distribution',
            'categories': categories_data,
            'total_category_revenue': round(sum(float(r) for r in forecast_data['category_revenues']), 2),
        }
        return payload, 200

    elif cleaned_type == 'top_products':
        kpis = get_dashboard_kpis()
        top_prods = _format_top_products(kpis['top_products'])
        payload = {
            'metric_type': 'top_products',
            'total_returned': len(top_prods),
            'top_products': top_prods,
        }
        return payload, 200

    elif cleaned_type == 'all':
        kpis = get_dashboard_kpis()
        forecast_data = get_forecast_data()
        categories_data = [
            {'category': label, 'revenue': float(rev)}
            for label, rev in zip(forecast_data['category_labels'], forecast_data['category_revenues'])
        ]
        payload = {
            'metric_type': 'all',
            'overview': {
                'current_month': kpis['current_month_name'],
                'monthly_revenue': float(kpis['monthly_revenue']),
                'monthly_orders': int(kpis['monthly_orders_count']),
                'avg_order_value': float(kpis['avg_order_value']),
                'active_customers': int(kpis['active_customers_count']),
                'abandoned_carts': int(kpis['abandoned_carts_count']),
                'top_product_star': _format_top_product_star(kpis['top_product_star']),
            },
            'forecast': {
                'historical_trend': {
                    'months': forecast_data['months_labels'],
                    'revenue': [float(r) for r in forecast_data['historical_revenue']],
                },
                'forecast_3_months': {
                    'months': forecast_data['forecast_months'],
                    'projected_revenue': [float(r) for r in forecast_data['forecast_revenue']],
                    'upper_bound': [float(r) for r in forecast_data['forecast_upper']],
                    'lower_bound': [float(r) for r in forecast_data['forecast_lower']],
                },
                'next_month_projected': float(forecast_data['next_month_projected']),
                'mom_growth_pct': float(forecast_data['mom_growth']),
                'seasonality_index': float(forecast_data['seasonality_index']),
            },
            'category_distribution': {
                'categories': categories_data,
                'total_category_revenue': round(sum(float(r) for r in forecast_data['category_revenues']), 2),
            },
            'top_products': _format_top_products(kpis['top_products']),
        }
        return payload, 200

    return {
        'error': 'Bad Request',
        'detail': 'Invalid metric_type. Supported values: overview, kpis, forecast, sales_trend, category_distribution, top_products, all',
    }, 400
