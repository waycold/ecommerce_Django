"""
config/urls.py

Primary URL routing configuration for ecommerce_Django.
Dispatches requests to clean modular apps:
- /admin/ -> Django Administration
- /analytics/ -> Managerial Business Analytics Portal & AI Chat
- /api/v1/internal/ -> Internal Microservice & Orchestrator APIs
- / -> E-Commerce Storefront, Product Catalog & Order Processing
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve

from apps.orders.views import login_view
from apps.catalog.urls import urlpatterns as catalog_urls
from apps.orders.urls import urlpatterns as orders_urls

# Combined pattern for backwards compatibility with 'product' namespace
product_legacy_patterns = (catalog_urls + orders_urls, 'product')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', login_view, name='login'),
    
    # Modular Apps with dedicated namespaces
    path('analytics/', include('apps.analytics.urls', namespace='analytics')),
    path('api/v1/internal/', include('apps.core.internal_urls', namespace='internal')),
    path('orders/', include('apps.orders.urls', namespace='orders')),
    path('catalog/', include('apps.catalog.urls', namespace='catalog')),
    
    # Direct Root Storefront access (e.g. '/', '/product/<slug>/', '/checkout/')
    path('', include(product_legacy_patterns, namespace='product')),
    
    # Media and Upload File Serving
    re_path(r'^uploads/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
