from django.urls import path
from django.contrib.auth.decorators import login_required

from product.views import (
    log_in,
    log_out,
    sign_up,
    about,
    add_to_cart,
    remove_from_cart,
    CheckoutView,
    HomeView,
    profile,
    edit_profile,
    remove_single_cart,
    delete,
    ProductDetailView,
    agregar_imagen,
    create_product,
    edit_product,
)

app_name = 'product'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('logout/', log_out),
    path('signup/', sign_up),
    path('login/', log_in),
    path('profile/', login_required(profile)),
    path('create_product/', create_product),
    path('edit_product/<slug>/', edit_product, name='edit_product'),
    path('edit_profile/<username>/', login_required(edit_profile), name='edit_profile'),
    path('product/<slug>/', ProductDetailView.as_view(), name='product'),
    path('about/', about),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('add_to_cart/<slug>/', login_required(add_to_cart), name='add_to_cart'),
    path('remove_single_cart/<slug>/', login_required(remove_single_cart), name='remove_single_from_cart'),
    path('remove-from-cart/<slug>/', login_required(remove_from_cart), name='remove-from-cart'),
    path('delete/<slug>/', login_required(delete), name='delete'),
    path('agregar_imagen', login_required(agregar_imagen), name='agregar_imagen'),
]
