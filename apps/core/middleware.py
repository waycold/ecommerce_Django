"""
apps.core.middleware

Internal service security middleware for service-to-service authentication.
Intercepts requests starting with /api/v1/internal/ and validates the X-Internal-Secret header.
"""

from django.conf import settings
from django.http import JsonResponse


class InternalSecretMiddleware:
    """
    Middleware that protects all `/api/v1/internal/*` endpoints.
    Requires the `X-Internal-Secret` HTTP header matching `settings.INTERNAL_API_SECRET`.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/v1/internal/'):
            secret_header = (
                request.headers.get('X-Internal-Secret')
                or request.META.get('HTTP_X_INTERNAL_SECRET')
            )
            expected_secret = getattr(settings, 'INTERNAL_API_SECRET', None)

            if not secret_header or secret_header != expected_secret:
                return JsonResponse(
                    {
                        'error': 'Unauthorized',
                        'detail': 'Invalid or missing X-Internal-Secret header.'
                    },
                    status=401
                )

        return self.get_response(request)
