"""
apps/core/internal_urls.py

Internal Microservice URL Routing for AI Agent & Orchestrator Communication.
All endpoints are secured by InternalSecretMiddleware requiring X-Internal-Secret.
Supports both trailing-slash and non-trailing-slash requests seamlessly.
"""

from django.urls import re_path

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
    catalog_vector_search_view,
    catalog_embeddings_similar_view,
    catalog_embeddings_pending_view,
    catalog_embeddings_upsert_view,
    catalog_embeddings_mark_error_view,
    catalog_items_verify_view,
    catalog_facets_view,
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
    re_path(r'^health/?$', health_check_view, name='internal_health'),
    
    # Auth & Security
    re_path(r'^auth/validate-token/?$', validate_token_view, name='internal_auth_validate_token'),
    
    # Catalog & Inventory
    re_path(r'^catalog/search/?$', catalog_search_view, name='internal_catalog_search'),
    re_path(r'^catalog/semantic-search/?$', catalog_semantic_search_view, name='internal_catalog_semantic_search'),
    re_path(r'^catalog/reviews-summary/?$', catalog_reviews_summary_view, name='internal_catalog_reviews_summary'),
    re_path(r'^inventory/health/?$', inventory_health_view, name='internal_inventory_health'),
    
    # Analytics, Metrics & Reporting
    re_path(r'^analytics/metrics/?$', analytics_metrics_view, name='internal_analytics_metrics'),
    re_path(r'^analytics/query/?$', analytics_query_view, name='internal_analytics_query'),
    re_path(r'^analytics/margins/?$', analytics_margins_view, name='internal_analytics_margins'),
    re_path(r'^analytics/funnel/?$', analytics_funnel_view, name='internal_analytics_funnel'),
    
    # Customers & CRM
    re_path(r'^customers/insights/?$', customer_insights_view, name='internal_customers_insights'),
    
    # Safe SQL Sandbox
    re_path(r'^query/raw-read/?$', raw_sql_sandbox_view, name='internal_raw_sql_sandbox'),

    # RAG / pgvector Catalog Endpoints
    re_path(r'^catalog/vector-search/?$', catalog_vector_search_view, name='internal_catalog_vector_search'),
    re_path(r'^catalog/embeddings/similar/?$', catalog_embeddings_similar_view, name='internal_catalog_embeddings_similar'),
    re_path(r'^catalog/embeddings/pending/?$', catalog_embeddings_pending_view, name='internal_catalog_embeddings_pending'),
    re_path(r'^catalog/embeddings/upsert/?$', catalog_embeddings_upsert_view, name='internal_catalog_embeddings_upsert'),
    re_path(r'^catalog/embeddings/mark-error/?$', catalog_embeddings_mark_error_view, name='internal_catalog_embeddings_mark_error'),
    re_path(r'^catalog/items/verify/?$', catalog_items_verify_view, name='internal_catalog_items_verify'),
    re_path(r'^catalog/facets/?$', catalog_facets_view, name='internal_catalog_facets'),
]
