from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import logout, login, authenticate
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.generic import DetailView, View

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from product.models import Item, OrderItem, Order, Profile, Comments, Category, Brand, Supplier, OrderStatus, PaymentMethod
from product.forms import (
    profile_edit_form,
    comments_form,
    image_form,
    product_form,
    edit_product_form,
)


def superuser_required(view_func):
    return user_passes_test(lambda u: u.is_superuser)(view_func)


class HomeView(View):
    template_name = 'home.html'

    def _filter_items(self, request):
        items = Item.objects.filter(is_active=True, stock__gt=0).order_by('-id')
        search_query = request.GET.get('search') or request.POST.get('search')
        category_id = request.GET.get('category_id') or request.POST.get('category_id')

        if search_query:
            items = items.filter(
                Q(category__name__icontains=search_query) |
                Q(brand__name__icontains=search_query) |
                Q(title__icontains=search_query)
            ).distinct()
        elif category_id:
            items = items.filter(category_id=category_id)

        return items, search_query, category_id

    def get(self, request):
        items, search_query, category_id = self._filter_items(request)

        paginator = Paginator(items, 16)
        page_number = request.GET.get('page')
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return render(request, self.template_name, {
            'page_obj': page_obj,
            'items': page_obj.object_list,
            'categories': Category.objects.all(),
            'search': search_query,
            'selected_category': int(category_id) if category_id and str(category_id).isdigit() else None,
        })

    def post(self, request):
        return self.get(request)


class ProductDetailView(DetailView):
    model = Item
    template_name = 'product.html'
    slug_url_kwarg = 'slug'
    context_object_name = 'object'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = Item.objects.filter(slug=self.kwargs['slug'])
        context['comments'] = Comments.objects.filter(item=self.object)
        context['form'] = comments_form()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        slug = self.kwargs['slug']

        if 'delete' in request.POST:
            if not request.user.is_superuser:
                messages.error(request, 'You do not have permission to delete products.')
                return redirect('product:product', slug=slug)
            self.object.delete()
            return redirect('/')

        if 'submit' in request.POST:
            if not request.user.is_authenticated:
                return redirect('product:login')

            form = comments_form(request.POST)
            if form.is_valid():
                Comments.objects.create(
                    user=request.user,
                    item=self.object,
                    body=form.cleaned_data['body'],
                )
            else:
                messages.error(request, 'Could not post your comment.')

        return redirect('product:product', slug=slug)


def sign_up(request):
    if request.method == 'GET':
        return render(request, 'signup.html', {'form': UserCreationForm})

    if request.POST['password1'] != request.POST['password2']:
        return render(request, 'signup.html', {
            'form': UserCreationForm,
            'error': 'Passwords do not match',
        })

    try:
        user = User.objects.create_user(
            username=request.POST['username'],
            password=request.POST['password1'],
        )
        Profile.objects.create(user=user)
        login(request, user)
        return redirect('/')
    except IntegrityError:
        return render(request, 'signup.html', {
            'form': UserCreationForm,
            'error': 'User already exists',
        })


def log_out(request):
    logout(request)
    return redirect('/')


def log_in(request):
    if request.method == 'GET':
        return render(request, 'login.html', {'form': AuthenticationForm})

    user = authenticate(
        request,
        username=request.POST['username'],
        password=request.POST['password'],
    )
    if user is None:
        return render(request, 'login.html', {
            'form': AuthenticationForm,
            'error': 'User or password is incorrect',
        })

    login(request, user)
    return redirect('/')


def agregar_imagen(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = image_form(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('/profile')
    else:
        form = image_form(instance=profile)

    return render(request, 'profile.html', {'image_form': form, 'user_profile': profile})


def about(request):
    return render(request, 'about.html', {
        'items': Item.objects.all(),
        'categories': Category.objects.all(),
    })


@superuser_required
def create_product(request):
    if request.method == 'POST':
        form = product_form(request.POST, request.FILES)
        if form.is_valid():
            title = form.cleaned_data['title']
            if Item.objects.filter(title=title).exists():
                messages.info(request, 'That title already exists')
                return render(request, 'create_product.html', {'form': form})
            form.save()
            return redirect('/')
    else:
        form = product_form()

    return render(request, 'create_product.html', {'form': form})


@superuser_required
def edit_product(request, slug):
    product = get_object_or_404(Item, slug=slug)

    if request.method == 'GET':
        return render(request, 'edit_product.html', {
            'form': edit_product_form(instance=product),
        })

    form = edit_product_form(request.POST, request.FILES, instance=product)
    if not form.is_valid():
        messages.info(request, 'Error updating product data.')
        return render(request, 'edit_product.html', {'form': form})

    title = form.cleaned_data['title']
    if Item.objects.filter(title=title).exclude(pk=product.pk).exists():
        messages.info(request, 'That title already exists')
        return render(request, 'edit_product.html', {'form': form})

    form.save()
    return redirect('/')


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
            messages.info(request, 'No tienes un carrito activo')
            return redirect('product:order_summary')

        if 'delete' in request.POST:
            for order_item in list(order.items.all()):
                order.items.remove(order_item)
                order_item.delete()
            order.delete()
            messages.info(request, 'Tu carrito ha sido vaciado.')
            return redirect('product:order_summary')

        if 'apply_discount' in request.POST:
            code = request.POST.get('discount_code', '').strip().upper()
            if code in ['DESC10', 'PROMO10']:
                order.discount_code = code
                order.calculate_total()
                order.save()
                messages.info(request, f'¡Código "{code}" aplicado! Se descontó un 10%.')
            elif code in ['OFF500', 'DESCUENTO']:
                order.discount_code = code
                order.calculate_total()
                order.save()
                messages.info(request, f'¡Código "{code}" aplicado! Se descontaron $500.00.')
            else:
                messages.error(request, 'Código de descuento no válido. Prueba con DESC10 o OFF500.')

            return redirect('product:order_summary')

        return redirect('product:order_summary')


class CheckoutView(LoginRequiredMixin, View):
    login_url = '/login/'

    def _get_active_order(self, user):
        return Order.objects.filter(user=user, status=OrderStatus.PENDING).first()

    def get(self, request, *args, **kwargs):
        order = self._get_active_order(request.user)

        if not order or not order.items.exists():
            messages.info(request, 'Tu carrito está vacío. Agrega productos antes de realizar el checkout.')
            return redirect('product:order_summary')

        # Tarifa Plana de Envío (ej. $500.00)
        order.shipping_cost = 500.00
        order.calculate_total()
        order.save()

        user_profile, created = Profile.objects.get_or_create(user=request.user)

        return render(request, 'checkout.html', {
            'object': order,
            'payment_methods': PaymentMethod.choices,
            'user_profile': user_profile,
        })

    def post(self, request, *args, **kwargs):
        order = self._get_active_order(request.user)

        if not order or not order.items.exists():
            messages.info(request, 'Tu carrito está vacío.')
            return redirect('product:order_summary')

        payment_method = request.POST.get('payment_method', PaymentMethod.CREDIT_CARD)
        order.payment_method = payment_method
        order.shipping_cost = 500.00
        order.status = OrderStatus.PAID
        order.ordered_date = timezone.now()

        for order_item in order.items.all():
            order_item.unit_price = order_item.item.price
            order_item.unit_cost = order_item.item.cost
            order_item.subtotal = order_item.quantity * order_item.unit_price
            order_item.save()

            if order_item.item.stock > 0:
                order_item.item.stock = max(0, order_item.item.stock - order_item.quantity)
                order_item.item.save()

        order.calculate_total()
        order.save()

        messages.info(request, '¡Tu compra ha sido realizada con éxito!')
        return redirect('/')


def profile(request):
    user_profile, created = Profile.objects.get_or_create(user=request.user)
    return render(request, 'profile.html', {
        'user_profile': user_profile,
        'form': profile_edit_form(instance=user_profile),
        'image_form': image_form(instance=user_profile),
    })


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


def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)

    if item.stock <= 0:
        messages.error(request, f'El producto "{item.title}" no tiene stock disponible.')
        referer = request.META.get('HTTP_REFERER')
        if referer and ('/product/' in referer or '/order-summary' in referer):
            return redirect(referer)
        return redirect('product:order_summary')

    order, created = Order.objects.get_or_create(
        user=request.user,
        status=OrderStatus.PENDING,
    )

    order_item, item_created = OrderItem.objects.get_or_create(
        order=order,
        item=item,
    )

    current_qty = order_item.quantity if not item_created else 0
    if current_qty + 1 > item.stock:
        if item_created:
            order_item.delete()
        messages.warning(request, f'No puedes agregar más unidades de "{item.title}". Stock máximo disponible: {item.stock}.')
        return redirect('product:order_summary')

    if not item_created:
        order_item.quantity += 1
    else:
        order_item.quantity = 1

    order_item.unit_price = item.price
    order_item.unit_cost = item.cost
    order_item.subtotal = order_item.quantity * order_item.unit_price
    order_item.save()

    if order_item not in order.items.all():
        order.items.add(order_item)

    order.calculate_total()
    order.save()

    messages.info(request, f'"{item.title}" fue agregado a tu carrito.')
    return redirect('product:order_summary')


def remove_single_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order = Order.objects.filter(user=request.user, status=OrderStatus.PENDING).first()

    if not order:
        messages.info(request, 'No tienes un carrito activo')
        return redirect('product:order_summary')

    order_item = OrderItem.objects.filter(order=order, item=item).first()
    if not order_item:
        messages.info(request, 'Este producto no estaba en tu carrito')
        return redirect('product:order_summary')

    order_item.quantity -= 1
    if order_item.quantity <= 0:
        order.items.remove(order_item)
        order_item.delete()
    else:
        order_item.subtotal = order_item.quantity * order_item.unit_price
        order_item.save()

    order.calculate_total()
    order.save()
    return redirect('product:order_summary')


def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order = Order.objects.filter(user=request.user, status=OrderStatus.PENDING).first()

    if not order:
        messages.info(request, 'No tienes un carrito activo')
        return redirect('product:order_summary')

    order_item = OrderItem.objects.filter(order=order, item=item).first()
    if order_item:
        order.items.remove(order_item)
        order_item.delete()

    order.calculate_total()
    order.save()
    messages.info(request, 'Producto eliminado del carrito.')
    return redirect('product:order_summary')


def delete(request, slug):
    order = Order.objects.filter(user=request.user, status=OrderStatus.PENDING).first()
    if order:
        for order_item in list(order.items.all()):
            order.items.remove(order_item)
            order_item.delete()
        order.delete()
    return redirect('product:order_summary')
