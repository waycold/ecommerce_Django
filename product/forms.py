from django import forms
from product.models import Profile, Comments, Item, Category, Brand, Supplier


class profile_edit_form(forms.ModelForm):
    birth_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = Profile
        fields = ['phone', 'description', 'address_line', 'city', 'province', 'zip_code', 'country', 'birth_date']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono'}),
            'address_line': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Calle y número, piso, dpto'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ciudad'}),
            'province': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Provincia / Estado / Región'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Código Postal'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'País'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción'}),
        }


class comments_form(forms.ModelForm):
    body = forms.CharField(
        label='',
        widget=forms.Textarea(attrs={'placeholder': 'Escribe tu comentario aquí...', 'rows': 3, 'class': 'form-control'})
    )

    class Meta:
        model = Comments
        fields = ['body']


class image_form(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['image']


class product_form(forms.ModelForm):
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False, widget=forms.Select(attrs={'class': 'form-control'}))
    brand = forms.ModelChoiceField(queryset=Brand.objects.all(), required=False, widget=forms.Select(attrs={'class': 'form-control'}))
    supplier = forms.ModelChoiceField(queryset=Supplier.objects.all(), required=False, widget=forms.Select(attrs={'class': 'form-control'}))

    class Meta:
        model = Item
        fields = ['title', 'description', 'price', 'cost', 'stock', 'minimum_stock', 'category', 'brand', 'supplier', 'label', 'img', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Título del producto'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Precio de venta'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Costo'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Stock actual'}),
            'minimum_stock': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Stock mínimo'}),
            'label': forms.Select(attrs={'class': 'form-control'}),
            'img': forms.FileInput(attrs={'class': 'form-control-file'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class edit_product_form(product_form):
    pass
