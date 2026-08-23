"""
apps/core/internal_views.py

Internal API HTTP controllers for raw read-only SQL execution sandbox.
Secured by InternalSecretMiddleware and consumed by AI Agents for dynamic ad-hoc analysis.
"""

import json
from django.http import JsonResponse
from apps.core.services.sql_sandbox_service import execute_safe_sql_sandbox


def raw_sql_sandbox_view(request):
    """
    POST /api/v1/internal/query/raw-read/

    Request Body:
        {
            "query": "SELECT category_id, COUNT(*) FROM product_item GROUP BY category_id;"
        }

    Returns:
        JsonResponse: 200 with columns, rows, execution_time_ms; 400 on invalid or unsafe queries; 405 on non-POST.
    """
    if request.method != 'POST':
        return JsonResponse(
            {
                'error': 'Method Not Allowed',
                'detail': f'Method {request.method} not allowed. Must be POST.',
            },
            status=405,
        )

    try:
        body_content = request.body.decode('utf-8') if isinstance(request.body, bytes) else str(request.body)
        data = json.loads(body_content) if body_content else {}
    except Exception:
        return JsonResponse(
            {
                'error': 'Bad Request',
                'detail': 'Invalid JSON body in request.',
            },
            status=400,
        )

    query_str = data.get('query') or data.get('sql') or ""
    result, status_code = execute_safe_sql_sandbox(raw_query=query_str)
    return JsonResponse(result, status=status_code)
