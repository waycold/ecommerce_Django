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
        norm_path = '/' + request.path.lstrip('/')
        if norm_path.startswith('/api/v1/internal/'):
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

            # The Gateway is a server-to-server client: it authenticates with
            # this shared secret, never with a browser session/CSRF cookie,
            # so CsrfViewMiddleware's cookie-based check doesn't apply to it.
            # `csrf_processing_done` is the exact flag
            # django.middleware.csrf.CsrfViewMiddleware.process_view checks
            # first ("if getattr(request, 'csrf_processing_done', False):
            # return None") to skip its own check. Setting it here -- once
            # the secret has already validated -- exempts every current and
            # future /api/v1/internal/* view centrally, instead of requiring
            # a @csrf_exempt decorator on each one (a fix that already
            # regressed twice when new POST views were added without it).
            request.csrf_processing_done = True

        return self.get_response(request)
