from django.urls import path
from apps.core.views import health_check_view
from apps.core.authentication.views import validate_token_view
from apps.catalog.internal_views import catalog_search_view
from apps.analytics.internal_views import analytics_metrics_view

app_name = 'internal'

urlpatterns = [
    path('health/', health_check_view, name='internal_health'),
    path('catalog/search/', catalog_search_view, name='internal_catalog_search'),
    path('auth/validate-token/', validate_token_view, name='internal_auth_validate_token'),
    path('analytics/metrics/', analytics_metrics_view, name='internal_analytics_metrics'),
]
