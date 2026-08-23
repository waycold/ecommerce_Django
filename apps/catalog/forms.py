from django import forms
from apps.catalog.models import Comments, Item, Category, Brand, Supplier


class comments_form(forms.ModelForm):
    body = forms.CharField(
        label='',
        widget=forms.Textarea(attrs={'placeholder': 'Write your comment here...', 'rows': 3, 'class': 'form-control'})
    )
    rating = forms.IntegerField(
        min_value=1,
        max_value=5,
        initial=5,
        widget=forms.HiddenInput(attrs={'id': 'id_rating_hidden'})
    )

    class Meta:
        model = Comments
        fields = ['body', 'rating']


class product_form(forms.ModelForm):
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False, widget=forms.Select(attrs={'class': 'form-control'}))
    brand = forms.ModelChoiceField(queryset=Brand.objects.all(), required=False, widget=forms.Select(attrs={'class': 'form-control'}))
    supplier = forms.ModelChoiceField(queryset=Supplier.objects.all(), required=False, widget=forms.Select(attrs={'class': 'form-control'}))

    class Meta:
        model = Item
        fields = ['title', 'description', 'price', 'cost', 'stock', 'minimum_stock', 'category', 'brand', 'supplier', 'label', 'img', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Price'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Cost'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Current Stock'}),
            'minimum_stock': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Minimum Stock'}),
            'label': forms.Select(attrs={'class': 'form-control'}),
            'img': forms.FileInput(attrs={'class': 'form-control-file'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class edit_product_form(product_form):
    pass
