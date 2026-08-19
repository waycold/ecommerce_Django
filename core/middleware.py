from django.conf import settings
from django.http import JsonResponse


class InternalSecretMiddleware:
    """
    Middleware that protects internal API routes (/api/v1/internal/*)
    by verifying the X-Internal-Secret header against settings.INTERNAL_API_SECRET.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/v1/internal/'):
            secret_header = (
                request.headers.get('X-Internal-Secret')
                if hasattr(request, 'headers')
                else None
            )
            if not secret_header:
                secret_header = request.META.get('HTTP_X_INTERNAL_SECRET')

            expected_secret = getattr(settings, 'INTERNAL_API_SECRET', None)

            if not secret_header or not expected_secret or secret_header != expected_secret:
                return JsonResponse(
                    {
                        'error': 'Unauthorized',
                        'detail': 'Invalid or missing X-Internal-Secret header.',
                    },
                    status=401,
                )

        return self.get_response(request)
