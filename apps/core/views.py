from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
def health_check_view(request):
    """
    Healthcheck endpoint for internal service communication and orchestrator pings.
    """
    return JsonResponse({"status": "healthy", "service": "django-internal-api"})
