from django.contrib import messages
from django.contrib.auth import logout, login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View

from apps.orders.models import Order, OrderItem, Profile, OrderStatus, PaymentMethod
from apps.orders.forms import profile_edit_form, image_form
from apps.orders.services import (
    add_item_to_cart_service,
    remove_single_item_from_cart_service,
    remove_item_from_cart_service,
    apply_discount_service,
    process_checkout_service,
)
from apps.catalog.models import Item


def sign_up(request):
    if request.method == 'GET':
        return render(request, 'signup.html', {'form': UserCreationForm()})

    form = UserCreationForm(request.POST)
    if form.is_valid():
        user = form.save()
        Profile.objects.get_or_create(user=user)
        login(request, user)
        return redirect('/')
    else:
        error_msg = None
        for field, errors in form.errors.items():
            error_msg = f"{field}: {errors[0]}"
            break
        return render(request, 'signup.html', {
            'form': form,
            'error': error_msg or 'Invalid form data. Please check password requirements.',
        })


register_view = sign_up


def log_out(request):
    logout(request)
    return redirect('/')


logout_view = log_out


def log_in(request):
    if request.method == 'GET':
        return render(request, 'login.html', {'form': AuthenticationForm()})

    form = AuthenticationForm(request, data=request.POST)
    if form.is_valid():
        user = form.get_user()
        login(request, user)
        return redirect('/')
    else:
        return render(request, 'login.html', {
            'form': form,
            'error': 'User or password is incorrect',
        })


login_view = log_in


class OrderSummaryView(LoginRequiredMixin, View):
    login_url = '/login/'

    def _get_active_order(self, user):
        return Order.objects.filter(user=user, status=OrderStatus.PENDING).first()

    def get(self, request, *args, **kwargs):
        order = self._get_active_order(request.user)
        if order:
            order.calculate_total()
            order.save()
        return render(request, 'order_summary.html', {'object': order})

    def post(self, request, *args, **kwargs):
        order = self._get_active_order(request.user)

        if not order:
            messages.info(request, 'You do not have an active cart')
            return redirect('orders:order_summary')

        if 'delete' in request.POST:
            for order_item in list(order.items.all()):
                order.items.remove(order_item)
                order_item.delete()
            order.delete()
            messages.info(request, 'Your cart has been emptied.')
            return redirect('orders:order_summary')

        if 'apply_discount' in request.POST:
            code = request.POST.get('discount_code', '').strip().upper()
            success, msg = apply_discount_service(request.user, code)
            if success:
                messages.info(request, msg)
            else:
                messages.error(request, msg)
            return redirect('orders:order_summary')

        return redirect('orders:order_summary')


class CheckoutView(LoginRequiredMixin, View):
    login_url = '/login/'

    def _get_active_order(self, user):
        return Order.objects.filter(user=user, status=OrderStatus.PENDING).first()

    def get(self, request, *args, **kwargs):
        order = self._get_active_order(request.user)

        if not order or not order.items.exists():
            messages.info(request, 'Your cart is empty. Add products before proceeding to checkout.')
            return redirect('orders:order_summary')

        order.shipping_cost = order.recalculate_shipping_cost()
        order.calculate_total()
        order.save()

        user_profile, created = Profile.objects.get_or_create(user=request.user)

        return render(request, 'checkout.html', {
            'object': order,
            'payment_methods': PaymentMethod.choices,
            'user_profile': user_profile,
        })

    def post(self, request, *args, **kwargs):
        payment_method = request.POST.get('payment_method', PaymentMethod.CREDIT_CARD)
        success, msg = process_checkout_service(request.user, payment_method)
        if success:
            messages.info(request, msg)
            return redirect('/')
        else:
            messages.info(request, msg)
            return redirect('orders:order_summary')


@login_required
def profile(request):
    user_profile, created = Profile.objects.get_or_create(user=request.user)
    return render(request, 'profile.html', {
        'user_profile': user_profile,
        'form': profile_edit_form(instance=user_profile),
        'image_form': image_form(instance=user_profile),
    })


class ProfileView(LoginRequiredMixin, View):
    login_url = '/login/'

    def get(self, request):
        return profile(request)


@login_required
def edit_profile(request, username):
    user_profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        return render(request, 'edit_profile.html', {
            'user_profile': user_profile,
            'form': profile_edit_form(instance=user_profile),
        })

    form = profile_edit_form(request.POST, request.FILES, instance=user_profile)
    if form.is_valid():
        form.save()
        messages.info(request, 'Profile updated successfully!')
        return redirect('/profile')

    messages.info(request, 'Error updating data.')
    return render(request, 'edit_profile.html', {
        'user_profile': user_profile,
        'form': form,
    })


class EditProfileView(LoginRequiredMixin, View):
    login_url = '/login/'

    def get(self, request, username):
        return edit_profile(request, username)

    def post(self, request, username):
        return edit_profile(request, username)


@login_required
def agregar_imagen(request):
    profile_obj, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = image_form(request.POST, request.FILES, instance=profile_obj)
        if form.is_valid():
            form.save()
            return redirect('/profile')
    else:
        form = image_form(instance=profile_obj)

    return render(request, 'profile.html', {'image_form': form, 'user_profile': profile_obj})


@login_required
def add_to_cart(request, slug):
    success, msg = add_item_to_cart_service(request.user, slug)
    if not success and 'stock' in msg.lower():
        messages.error(request, msg)
        referer = request.META.get('HTTP_REFERER')
        if referer and ('/product/' in referer or '/order-summary' in referer):
            return redirect(referer)
        return redirect('orders:order_summary')

    if success:
        messages.info(request, msg)
    else:
        messages.warning(request, msg)
    return redirect('orders:order_summary')


@login_required
def remove_single_cart(request, slug):
    success, msg = remove_single_item_from_cart_service(request.user, slug)
    if not success:
        messages.info(request, msg)
    return redirect('orders:order_summary')


remove_single_item_from_cart = remove_single_cart


@login_required
def remove_from_cart(request, slug):
    success, msg = remove_item_from_cart_service(request.user, slug)
    if success:
        messages.info(request, 'Producto eliminado del carrito.')
    else:
        messages.info(request, msg)
    return redirect('orders:order_summary')


@login_required
def delete(request, slug):
    order = Order.objects.filter(user=request.user, status=OrderStatus.PENDING).first()
    if order:
        for order_item in list(order.items.all()):
            order.items.remove(order_item)
            order_item.delete()
        order.delete()
    return redirect('orders:order_summary')


@login_required
def apply_coupon_view(request):
    if request.method == 'POST':
        code = request.POST.get('discount_code', '').strip().upper()
        success, msg = apply_discount_service(request.user, code)
        if success:
            messages.info(request, msg)
        else:
            messages.error(request, msg)
    return redirect('orders:order_summary')
