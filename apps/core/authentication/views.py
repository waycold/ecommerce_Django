"""
apps/core/authentication/views.py

Internal API HTTP controllers for staff token validation.
Secured by InternalSecretMiddleware.
"""

import json
from django.http import JsonResponse
from apps.core.authentication.services import validate_staff_jwt_token


def validate_token_view(request):
    """
    POST /api/v1/internal/auth/validate-token/

    Request Body:
        {
            "token": "<jwt_token_string>"
        }

    Returns:
        - 200: Valid staff/admin user
        - 400: Missing/malformed token payload or invalid JSON
        - 401: Expired, invalid token, or inactive user
        - 403: Valid user but lacks staff permissions
        - 405: Method not allowed (non-POST)
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
        data = json.loads(body_content)
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return JsonResponse(
            {
                'error': 'Bad Request',
                'detail': 'Missing or invalid token parameter.',
            },
            status=400,
        )

    if not isinstance(data, dict):
        return JsonResponse(
            {
                'error': 'Bad Request',
                'detail': 'Missing or invalid token parameter.',
            },
            status=400,
        )

    token = data.get('token')
    if not token or not isinstance(token, str) or not token.strip():
        return JsonResponse(
            {
                'error': 'Bad Request',
                'detail': 'Missing or invalid token parameter.',
            },
            status=400,
        )

    response_data, status_code = validate_staff_jwt_token(token.strip())
    return JsonResponse(response_data, status=status_code)
