from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from product.views import log_in

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', log_in, name='login'),
    path('analytics/', include('analytics.urls', namespace='analytics')),
    path('', include('product.urls', namespace='product'))
]

if settings.DEBUG:
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)