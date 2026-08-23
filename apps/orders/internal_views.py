"""
apps/orders/internal_views.py

Internal API HTTP controllers for CRM insights, RFM customer segmentation,
and geographic revenue intelligence.
Secured by InternalSecretMiddleware and consumed by the AI orchestrator microservice.
"""

from django.http import JsonResponse
from apps.orders.services import get_customer_insights_service


def customer_insights_view(request):
    """
    GET /api/v1/internal/customers/insights/

    Query Parameters:
        - limit (optional, int): Max top customers to return (default 20, max 100).

    Returns:
        JsonResponse: 200 with RFM segmentation, LTV metrics, and geographic distribution.
    """
    if request.method != 'GET':
        return JsonResponse(
            {
                'error': 'Method Not Allowed',
                'detail': f'Method {request.method} not allowed. Must be GET.',
            },
            status=405,
        )

    limit_param = request.GET.get('limit', 20)
    try:
        limit = int(limit_param)
        if limit <= 0:
            return JsonResponse({'error': 'Bad Request', 'detail': 'Limit must be a positive integer.'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Bad Request', 'detail': 'Limit must be a positive integer.'}, status=400)

    result = get_customer_insights_service(limit=limit)
    return JsonResponse(result, status=200)
