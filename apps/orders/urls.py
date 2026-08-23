from django.urls import path
from apps.orders.views import (
    log_in,
    log_out,
    sign_up,
    add_to_cart,
    remove_from_cart,
    OrderSummaryView,
    CheckoutView,
    profile,
    edit_profile,
    remove_single_cart,
    delete,
    agregar_imagen,
    apply_coupon_view,
)

app_name = 'orders'

urlpatterns = [
    path('logout/', log_out, name='logout'),
    path('signup/', sign_up, name='signup'),
    path('login/', log_in, name='login'),
    path('profile/', profile, name='profile'),
    path('edit_profile/<str:username>/', edit_profile, name='edit_profile'),
    path('order-summary/', OrderSummaryView.as_view(), name='order_summary'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('add_to_cart/<slug:slug>/', add_to_cart, name='add_to_cart'),
    path('remove_single_cart/<slug:slug>/', remove_single_cart, name='remove_single_from_cart'),
    path('remove-from-cart/<slug:slug>/', remove_from_cart, name='remove-from-cart'),
    path('delete/<slug:slug>/', delete, name='delete'),
    path('agregar_imagen', agregar_imagen, name='agregar_imagen'),
    path('apply-coupon/', apply_coupon_view, name='apply_coupon'),
]
