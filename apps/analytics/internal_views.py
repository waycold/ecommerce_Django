"""
apps/analytics/internal_views.py

Internal API HTTP controllers for business analytics and metrics retrieval.
Secured by InternalSecretMiddleware and consumed by the AI orchestrator microservice.
"""

from django.http import JsonResponse
from apps.analytics.services import get_internal_metrics_service


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
