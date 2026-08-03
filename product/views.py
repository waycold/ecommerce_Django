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

from product.models import Item, OrderItem, Order, Profile, Comments
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
        items = Item.objects.all()
        search_query = request.POST.get('search')

        if search_query:
            items = items.filter(
                Q(category__icontains=search_query) |
                Q(title__icontains=search_query)
            ).distinct()
        elif 'CPU' in request.POST:
            items = items.filter(category='CPU')
        elif 'GPU' in request.POST:
            items = items.filter(category='GPU')
        elif 'RAM' in request.POST:
            items = items.filter(category='RAM')

        return items, search_query

    def get(self, request):
        return render(request, self.template_name, {
            'items': Item.objects.all(),
            'search': None,
        })

    def post(self, request):
        items, search_query = self._filter_items(request)
        return render(request, self.template_name, {
            'items': items,
            'search': search_query,
        })


class ProductDetailView(DetailView):
    model = Item
    template_name = 'product.html'
    slug_url_kwarg = 'slug'
    context_object_name = 'object'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = Item.objects.filter(slug=self.kwargs['slug'])
        context['comments'] = Comments.objects.filter(url=self.request.path)
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
                profile = Profile.objects.filter(username=request.user).first()
                Comments.objects.create(
                    user=request.user,
                    body=form.cleaned_data['body'],
                    url=request.path,
                    image_perfil=profile.image if profile and profile.image else None,
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
            'error': 'Password do not match',
        })

    try:
        user = User.objects.create_user(
            username=request.POST['username'],
            password=request.POST['password1'],
        )
        Profile.objects.create(username=user)
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
    profile = get_object_or_404(Profile, username=request.user)

    if request.method == 'POST':
        form = image_form(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('/')
    else:
        form = image_form(instance=profile)

    return render(request, 'profile.html', {'image_form': form})


def about(request):
    return render(request, 'about.html', {
        'items': Item.objects.all(),
        'orderitems': OrderItem.objects.all(),
        'profile': Profile.objects.all(),
    })


@superuser_required
def create_product(request):
    if request.method == 'POST':
        form = product_form(request.POST, request.FILES)
        if form.is_valid():
            title = form.cleaned_data['title']
            if Item.objects.filter(title=title).exists():
                messages.info(request, 'That title already exist')
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
        messages.info(request, 'Error updating data.')
        return render(request, 'edit_product.html', {'form': form})

    title = form.cleaned_data['title']
    if Item.objects.filter(title=title).exclude(pk=product.pk).exists():
        messages.info(request, 'That title already exist')
        return render(request, 'edit_product.html', {'form': form})

    form.save()
    return redirect('/')


class CheckoutView(LoginRequiredMixin, View):
    login_url = '/login/'

    def _get_active_order(self):
        return Order.objects.filter(user=self.request.user, ordered=False).first()

    def _build_context(self, order):
        return {
            'items': Item.objects.all(),
            'orderitems': order.items.all() if order else OrderItem.objects.none(),
            'comments': Comments.objects.all(),
            'object': order,
        }

    def _clear_cart(self, order):
        for order_item in list(order.items.all()):
            order.items.remove(order_item)
            order_item.delete()
        order.delete()

    def get(self, request, *args, **kwargs):
        order = self._get_active_order()
        return render(request, 'checkout.html', self._build_context(order))

    def post(self, request, *args, **kwargs):
        order = self._get_active_order()

        if not order:
            messages.info(request, 'You do not have an active order')
            return redirect('product:checkout')

        if 'delete' in request.POST:
            self._clear_cart(order)
            messages.info(request, 'Your cart has been cleared.')
            return redirect('product:checkout')

        if 'buy' in request.POST:
            if order.items.exists():
                order.ordered = True
                order.ordered_date = timezone.now()
                order.save()
                for order_item in order.items.all():
                    order_item.ordered = True
                    order_item.save()
                messages.info(request, 'Your purchase has been successful!')
                return redirect('/')
            messages.info(request, 'Your cart is empty.')
            return redirect('product:checkout')

        return redirect('product:checkout')


def profile(request):
    user_profile, created = Profile.objects.get_or_create(username=request.user)
    return render(request, 'profile.html', {
        'user_profile': user_profile,
        'profile': [user_profile],
        'form': profile_edit_form(instance=user_profile),
        'image_form': image_form(instance=user_profile),
    })


def edit_profile(request, username):
    user_profile = get_object_or_404(Profile, username=request.user)

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
    order_item, created = OrderItem.objects.get_or_create(
        item=item,
        user=request.user,
        ordered=False,
    )
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            return redirect('product:checkout')
        order.items.add(order_item)
        messages.info(request, 'This item was added to your cart.')
        return redirect('product:product', slug=slug)

    order = Order.objects.create(
        user=request.user,
        ordered_date=timezone.now(),
    )
    order.items.add(order_item)
    messages.info(request, 'This item was added to your cart.')
    return redirect('product:product', slug=slug)


def remove_single_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if not order_qs.exists():
        messages.info(request, 'You do not have an active order')
        return redirect('product:checkout')

    order = order_qs[0]
    if not order.items.filter(item__slug=item.slug).exists():
        messages.info(request, 'This item was not in your cart')
        return redirect('product:checkout')

    order_item = OrderItem.objects.filter(
        item=item,
        user=request.user,
        ordered=False,
    ).first()
    order_item.quantity -= 1
    order_item.save()
    if order_item.quantity == 0:
        order.items.remove(order_item)
        order_item.delete()
    return redirect('product:checkout')


def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if not order_qs.exists():
        messages.info(request, 'You do not have an active order')
        return redirect('product:product', slug=slug)

    order = order_qs[0]
    if not order.items.filter(item__slug=item.slug).exists():
        messages.info(request, 'This item was not in your cart')
        return redirect('product:product', slug=slug)

    order_item = OrderItem.objects.filter(
        item=item,
        user=request.user,
        ordered=False,
    ).first()
    order.items.remove(order_item)
    order_item.delete()
    messages.info(request, 'This item was removed from your cart.')
    return redirect('product:product', slug=slug)


def delete(request, slug):
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        for order_item in list(order.items.all()):
            order.items.remove(order_item)
            order_item.delete()
        order.delete()
    return redirect('product:checkout')
