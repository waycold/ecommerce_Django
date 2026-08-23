from django.urls import path
from apps.catalog.views import (
    HomeView,
    ProductDetailView,
    create_product,
    edit_product,
    about,
    like_comment_view,
)

app_name = 'catalog'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('product/<slug:slug>/', ProductDetailView.as_view(), name='product'),
    path('create_product/', create_product, name='create_product'),
    path('edit_product/<slug:slug>/', edit_product, name='edit_product'),
    path('about/', about, name='about'),
    path('comments/like/<int:comment_id>/', like_comment_view, name='like_comment'),
]
