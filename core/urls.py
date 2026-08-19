from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from product.views import log_in

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', log_in, name='login'),
    path('analytics/', include('analytics.urls', namespace='analytics')),
    path('api/v1/internal/', include('core.internal_urls')),
    path('', include('product.urls', namespace='product')),
    re_path(r'^uploads/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]