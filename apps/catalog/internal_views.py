"""
apps/catalog/internal_views.py

Internal API HTTP controllers for catalog searches, inventory health metrics,
review sentiment summaries, and semantic conceptual searches.
Secured by InternalSecretMiddleware and consumed by the AI orchestrator microservice.
"""

import json
from django.http import JsonResponse
from apps.catalog.services import (
    search_catalog_service,
    get_inventory_health_service,
    get_reviews_summary_service,
    semantic_catalog_search_service,
)


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


def inventory_health_view(request):
    """
    GET /api/v1/internal/inventory/health/

    Query Parameters:
        - limit (optional, int): Max critical items to return (default 20, max 100).

    Returns:
        JsonResponse: 200 with inventory health, valuation, and critical stockout alerts.
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

    result = get_inventory_health_service(limit=limit)
    return JsonResponse(result, status=200)


def catalog_reviews_summary_view(request):
    """
    GET /api/v1/internal/catalog/reviews-summary/

    Query Parameters:
        - item_id (optional, int): Filter by item ID
        - category (optional, str/int): Filter by category
        - brand (optional, str/int): Filter by brand
        - min_rating (optional, int): Minimum stars 1-5
        - max_rating (optional, int): Maximum stars 1-5
        - limit (optional, int): Max latest reviews (default 15, max 100)

    Returns:
        JsonResponse: 200 with review analytics, rating distributions, and sentiment feedback.
    """
    if request.method != 'GET':
        return JsonResponse(
            {
                'error': 'Method Not Allowed',
                'detail': f'Method {request.method} not allowed. Must be GET.',
            },
            status=405,
        )

    item_id = request.GET.get('item_id')
    category = request.GET.get('category')
    brand = request.GET.get('brand')
    min_rating = request.GET.get('min_rating')
    max_rating = request.GET.get('max_rating')
    limit_param = request.GET.get('limit', 15)

    try:
        limit = int(limit_param)
        if limit <= 0:
            return JsonResponse({'error': 'Bad Request', 'detail': 'Limit must be a positive integer.'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Bad Request', 'detail': 'Limit must be a positive integer.'}, status=400)

    result = get_reviews_summary_service(
        item_id=item_id,
        category=category,
        brand=brand,
        min_rating=min_rating,
        max_rating=max_rating,
        limit=limit,
    )
    return JsonResponse(result, status=200)


def catalog_semantic_search_view(request):
    """
    POST (or GET) /api/v1/internal/catalog/semantic-search/

    Request Body (POST) or Query Params (GET):
        - query_text (str): Free-form user/LLM shopping query
        - limit (optional, int): Max products to return (default 10, max 50)

    Returns:
        JsonResponse: 200 with intent-expanded search matches and semantic relevance ranks.
    """
    if request.method not in ('POST', 'GET'):
        return JsonResponse(
            {
                'error': 'Method Not Allowed',
                'detail': f'Method {request.method} not allowed. Must be POST or GET.',
            },
            status=405,
        )

    query_text = ""
    limit = 10

    if request.method == 'POST':
        try:
            body_content = request.body.decode('utf-8') if isinstance(request.body, bytes) else str(request.body)
            data = json.loads(body_content) if body_content else {}
            query_text = data.get('query_text') or data.get('q') or ""
            limit = data.get('limit', 10)
        except Exception:
            query_text = request.POST.get('query_text') or request.POST.get('q') or ""
            limit = request.POST.get('limit', 10)
    else:
        query_text = request.GET.get('query_text') or request.GET.get('q') or ""
        limit = request.GET.get('limit', 10)

    try:
        limit = int(limit)
        if limit <= 0:
            return JsonResponse({'error': 'Bad Request', 'detail': 'Limit must be a positive integer.'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Bad Request', 'detail': 'Limit must be a positive integer.'}, status=400)

    result = semantic_catalog_search_service(
        query_text=query_text,
        limit=limit,
        request=request,
    )
    return JsonResponse(result, status=200)
