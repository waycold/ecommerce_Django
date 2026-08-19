"""
product/internal_views.py

Internal API HTTP controllers for microservice communication.
These endpoints are secured by InternalSecretMiddleware and consumed by the AI orchestrator microservice.
"""

from django.http import JsonResponse
from product.services import search_catalog_service


def catalog_search_view(request):
    """
    GET /api/v1/internal/catalog/search/

    Query Parameters:
        - q (optional, str): Search query string.
        - category (optional, str/int): Filter by category ID or name.
        - limit (optional, int): Max products to return (default 10, max 50).

    Returns:
        JsonResponse: 200 with catalog search results, 400 on invalid params, 405 on invalid method.
    """
    if request.method != 'GET':
        return JsonResponse(
            {
                'error': 'Method Not Allowed',
                'detail': f'Method {request.method} not allowed. Must be GET.',
            },
            status=405,
        )

    q = request.GET.get('q', '').strip() or None
    category = request.GET.get('category', '').strip() or None
    limit_param = request.GET.get('limit')

    limit = 10
    if limit_param is not None:
        try:
            limit = int(limit_param)
            if limit <= 0:
                return JsonResponse(
                    {
                        'error': 'Bad Request',
                        'detail': 'Invalid limit parameter. Must be a positive integer.',
                    },
                    status=400,
                )
        except (ValueError, TypeError):
            return JsonResponse(
                {
                    'error': 'Bad Request',
                    'detail': 'Invalid limit parameter. Must be a positive integer.',
                },
                status=400,
            )

    results = search_catalog_service(
        query=q,
        category=category,
        limit=limit,
        request=request,
    )

    return JsonResponse(results, status=200)
