"""
apps/core/internal_urls.py

Internal Microservice URL Routing for AI Agent & Orchestrator Communication.
All endpoints are secured by InternalSecretMiddleware requiring X-Internal-Secret.
"""

from django.urls import path

# Core views
from apps.core.views import health_check_view
from apps.core.authentication.views import validate_token_view
from apps.core.internal_views import raw_sql_sandbox_view

# Catalog internal views
from apps.catalog.internal_views import (
    catalog_search_view,
    inventory_health_view,
    catalog_reviews_summary_view,
    catalog_semantic_search_view,
)

# Analytics internal views
from apps.analytics.internal_views import (
    analytics_metrics_view,
    analytics_query_view,
    analytics_margins_view,
    analytics_funnel_view,
)

# Orders internal views
from apps.orders.internal_views import customer_insights_view

app_name = 'internal'

urlpatterns = [
    # System & Health
    path('health/', health_check_view, name='internal_health'),
    
    # Auth & Security
    path('auth/validate-token/', validate_token_view, name='internal_auth_validate_token'),
    
    # Catalog & Inventory
    path('catalog/search/', catalog_search_view, name='internal_catalog_search'),
    path('catalog/semantic-search/', catalog_semantic_search_view, name='internal_catalog_semantic_search'),
    path('catalog/reviews-summary/', catalog_reviews_summary_view, name='internal_catalog_reviews_summary'),
    path('inventory/health/', inventory_health_view, name='internal_inventory_health'),
    
    # Analytics, Metrics & Reporting
    path('analytics/metrics/', analytics_metrics_view, name='internal_analytics_metrics'),
    path('analytics/query/', analytics_query_view, name='internal_analytics_query'),
    path('analytics/margins/', analytics_margins_view, name='internal_analytics_margins'),
    path('analytics/funnel/', analytics_funnel_view, name='internal_analytics_funnel'),
    
    # Customers & CRM
    path('customers/insights/', customer_insights_view, name='internal_customers_insights'),
    
    # Safe SQL Sandbox
    path('query/raw-read/', raw_sql_sandbox_view, name='internal_raw_sql_sandbox'),
]
