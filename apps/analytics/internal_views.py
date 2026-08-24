"""
apps/analytics/internal_views.py

Internal API HTTP controllers for business analytics, dynamic sales queries,
margin profitability breakdowns, and cart abandonment funnels.
Secured by InternalSecretMiddleware and consumed by the AI orchestrator microservice.
"""

from django.http import JsonResponse
from apps.analytics.services import (
    get_internal_metrics_service,
    dynamic_sales_query_service,
    calculate_margins_service,
    calculate_funnel_and_promotions_service,
)


def analytics_metrics_view(request):
    """
    GET /api/v1/internal/analytics/metrics/

    Query Parameters:
        - metric_type (optional, str): 'overview' | 'kpis' | 'forecast' | 'sales_trend' |
                                       'category_distribution' | 'top_products' | 'all' (default: 'overview').

    Returns:
        - 200: Successful metrics payload
        - 400: Invalid metric_type query parameter
        - 405: Method not allowed (non-GET requests)
    """
    if request.method != 'GET':
        return JsonResponse(
            {
                'error': 'Method Not Allowed',
                'detail': f'Method {request.method} not allowed. Must be GET.',
            },
            status=405,
        )

    metric_type = request.GET.get('metric_type', 'overview').lower().strip()
    payload, status_code = get_internal_metrics_service(metric_type=metric_type)
    return JsonResponse(payload, status=status_code)


def analytics_query_view(request):
    """
    GET /api/v1/internal/analytics/query/

    Query Parameters:
        - date_from (optional, str): YYYY-MM-DD
        - date_to (optional, str): YYYY-MM-DD
        - group_by (optional, str): day | week | month | quarter | category | brand | supplier | payment_method | country
        - metrics (optional, str): comma-separated metric names
        - status (optional, str): order status filter
        - limit (optional, int): max rows to return (default 20, max 100)

    Returns:
        - 200: Aggregated sales query result
        - 400: Invalid parameters
        - 405: Method not allowed
    """
    if request.method != 'GET':
        return JsonResponse(
            {
                'error': 'Method Not Allowed',
                'detail': f'Method {request.method} not allowed. Must be GET.',
            },
            status=405,
        )

    date_from = request.GET.get('date_from') or None
    date_to = request.GET.get('date_to') or None
    group_by = request.GET.get('group_by', 'category')
    metrics = request.GET.get('metrics', 'revenue,orders,units')
    status = request.GET.get('status') or None
    limit_param = request.GET.get('limit', 20)

    try:
        limit = int(limit_param)
        if limit <= 0:
            return JsonResponse({'error': 'Bad Request', 'detail': 'Limit must be a positive integer.'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Bad Request', 'detail': 'Limit must be a positive integer.'}, status=400)

    result = dynamic_sales_query_service(
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        metrics=metrics,
        status=status,
        limit=limit,
    )
    return JsonResponse(result, status=200)


def analytics_margins_view(request):
    """
    GET /api/v1/internal/analytics/margins/

    Query Parameters:
        - dimension (optional, str): product | category | brand | supplier (default: product)
        - order_by (optional, str): margin_desc | margin_asc | revenue_desc | profit_desc (default: margin_desc)
        - date_from (optional, str): YYYY-MM-DD
        - date_to (optional, str): YYYY-MM-DD
        - limit (optional, int): max rows to return (default 20, max 100)

    Returns:
        - 200: Profit margin report
        - 400: Invalid parameters
        - 405: Method not allowed
    """
    if request.method != 'GET':
        return JsonResponse(
            {
                'error': 'Method Not Allowed',
                'detail': f'Method {request.method} not allowed. Must be GET.',
            },
            status=405,
        )

    dimension = request.GET.get('dimension', 'product')
    order_by = request.GET.get('order_by', 'margin_desc')
    date_from = request.GET.get('date_from') or None
    date_to = request.GET.get('date_to') or None
    limit_param = request.GET.get('limit', 20)

    try:
        limit = int(limit_param)
        if limit <= 0:
            return JsonResponse({'error': 'Bad Request', 'detail': 'Limit must be a positive integer.'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Bad Request', 'detail': 'Limit must be a positive integer.'}, status=400)

    result = calculate_margins_service(
        dimension=dimension,
        order_by=order_by,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return JsonResponse(result, status=200)


def analytics_funnel_view(request):
    """
    GET /api/v1/internal/analytics/funnel/

    Query Parameters:
        - period (optional, str): last_7_days | last_30_days | last_90_days | last_year | all_time

    Returns:
        - 200: Conversion funnel, abandonment rates and promotions ROI report
        - 405: Method not allowed
    """
    if request.method != 'GET':
        return JsonResponse(
            {
                'error': 'Method Not Allowed',
                'detail': f'Method {request.method} not allowed. Must be GET.',
            },
            status=405,
        )

    period = request.GET.get('period', 'last_30_days')
    result = calculate_funnel_and_promotions_service(period=period)
    return JsonResponse(result, status=200)
