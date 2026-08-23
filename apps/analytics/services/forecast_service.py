"""
apps/analytics/services/forecast_service.py

Time-series sales forecasting, linear regression demand predictions,
seasonality index computation, and category distribution modeling.
"""

import math
from datetime import timedelta
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from apps.orders.models import Order, OrderItem, OrderStatus


def get_forecast_data() -> dict:
    """
    Computes time-series sales trend, linear demand forecasting for the next 3 months,
    category distribution, and cross-category market basket co-occurrences.
    """
    paid_statuses = [OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED]

    monthly_sales = Order.objects.filter(
        status__in=paid_statuses,
        ordered_date__isnull=False
    ).annotate(
        month=TruncMonth('ordered_date')
    ).values('month').annotate(
        revenue=Sum('total'),
        orders_count=Count('id')
    ).order_by('month')

    months_labels = []
    historical_revenue = []
    historical_orders = []

    for entry in monthly_sales:
        if entry['month']:
            months_labels.append(entry['month'].strftime('%b %Y'))
            historical_revenue.append(round(float(entry['revenue'] or 0.0), 2))
            historical_orders.append(entry['orders_count'])

    forecast_months = []
    forecast_revenue = []
    forecast_upper = []
    forecast_lower = []

    n = len(historical_revenue)
    if n > 1:
        x = list(range(n))
        y = historical_revenue
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))

        slope = (n * sum_xy - sum_x * sum_y) / max(1.0, (n * sum_x2 - sum_x ** 2))
        intercept = (sum_y - slope * sum_x) / n

        residuals = [y[i] - (slope * x[i] + intercept) for i in range(n)]
        std_err = math.sqrt(sum(r ** 2 for r in residuals) / max(1, n - 2)) if n > 2 else sum(y) * 0.05

        last_date = monthly_sales[n - 1]['month'] if n > 0 and monthly_sales[n - 1]['month'] else timezone.now()

        for step in range(1, 4):
            future_date = last_date + timedelta(days=30 * step)
            forecast_months.append(future_date.strftime('%b %Y (F)'))

            proj_val = max(0.0, slope * (n - 1 + step) + intercept)
            margin = std_err * (1.0 + 0.15 * step)

            forecast_revenue.append(round(proj_val, 2))
            forecast_upper.append(round(proj_val + margin, 2))
            forecast_lower.append(round(max(0.0, proj_val - margin), 2))
    else:
        now = timezone.now()
        for step in range(1, 4):
            future_date = now + timedelta(days=30 * step)
            forecast_months.append(future_date.strftime('%b %Y (F)'))
            forecast_revenue.append(0.0)
            forecast_upper.append(0.0)
            forecast_lower.append(0.0)

    cat_sales = OrderItem.objects.filter(
        order__status__in=paid_statuses
    ).values(
        'item__category__name'
    ).annotate(
        total_revenue=Sum('subtotal'),
        units_sold=Sum('quantity')
    ).order_by('-total_revenue')[:8]

    category_labels = [c['item__category__name'] or 'Uncategorized' for c in cat_sales]
    category_revenues = [round(float(c['total_revenue'] or 0.0), 2) for c in cat_sales]

    next_month_projected = forecast_revenue[0] if forecast_revenue else 0.0
    last_revenue = historical_revenue[-1] if historical_revenue else 0.0
    prev_revenue = historical_revenue[-2] if len(historical_revenue) > 1 else last_revenue
    mom_growth = round(((last_revenue - prev_revenue) / max(1.0, prev_revenue)) * 100, 1)

    avg_monthly_rev = sum(historical_revenue) / max(1, len(historical_revenue)) if historical_revenue else 1.0
    max_rev = max(historical_revenue) if historical_revenue else 1.0
    seasonality_index = round(max_rev / max(1.0, avg_monthly_rev), 2)

    return {
        'months_labels': months_labels,
        'historical_revenue': historical_revenue,
        'forecast_months': forecast_months,
        'forecast_revenue': forecast_revenue,
        'forecast_upper': forecast_upper,
        'forecast_lower': forecast_lower,
        'category_labels': category_labels,
        'category_revenues': category_revenues,
        'next_month_projected': next_month_projected,
        'mom_growth': mom_growth,
        'seasonality_index': seasonality_index,
    }
