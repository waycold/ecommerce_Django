from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import DetailView, View
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from apps.catalog.models import Item, Comments, Category, Brand, Supplier
from apps.catalog.forms import comments_form, product_form, edit_product_form


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

        user_already_commented = False
        if self.request.user.is_authenticated:
            user_already_commented = Comments.objects.filter(user=self.request.user, item=self.object).exists()
        context['user_already_commented'] = user_already_commented
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        slug = self.kwargs['slug']

        if 'delete' in request.POST:
            if not request.user.is_superuser:
                messages.error(request, 'You do not have permission to delete products.')
                return redirect('catalog:product', slug=slug)
            self.object.delete()
            return redirect('/')

        if 'submit' in request.POST:
            if not request.user.is_authenticated:
                return redirect('orders:login')

            # Check if user already commented
            if Comments.objects.filter(user=request.user, item=self.object).exists():
                messages.error(request, 'You have already reviewed this product.')
                return redirect('catalog:product', slug=slug)

            form = comments_form(request.POST)
            if form.is_valid():
                Comments.objects.create(
                    user=request.user,
                    item=self.object,
                    body=form.cleaned_data['body'],
                    rating=form.cleaned_data['rating'],
                )
            else:
                messages.error(request, 'Could not post your comment.')

        return redirect('catalog:product', slug=slug)


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


class CreateProductView(UserPassesTestMixin, View):
    template_name = 'create_product.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request):
        return render(request, self.template_name, {'form': product_form()})

    def post(self, request):
        return create_product(request)


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


class EditProductView(UserPassesTestMixin, View):
    template_name = 'edit_product.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request, slug):
        return edit_product(request, slug)

    def post(self, request, slug):
        return edit_product(request, slug)


def about(request):
    return render(request, 'about.html', {
        'items': Item.objects.all(),
        'categories': Category.objects.all(),
    })


class AboutView(View):
    def get(self, request):
        return about(request)


@login_required
def like_comment_view(request, comment_id):
    comment = get_object_or_404(Comments, id=comment_id)
    comment.likes += 1
    comment.save(update_fields=['likes'])
    return JsonResponse({'status': 'success', 'likes': comment.likes})
