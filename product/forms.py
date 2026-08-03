from django import forms
from product.models import Profile, Comments, Item, CATEGORY_CHOICES

class profile_edit_form(forms.ModelForm):
    user = forms.CharField()
    email = forms.EmailField()
    phone = forms.DecimalField()
    description = forms.CharField()
    class Meta:
        model = Profile
        fields= ['user', 'email', 'phone', 'description'] 

class comments_form(forms.ModelForm):
    body = forms.CharField(label = '', widget = forms.Textarea(attrs={'placeholder': 'text here...', 'rows': 3, 'cols': 70}))
    requered_css_class = 'required-field'
    class Meta:
        model = Comments
        fields= ['body']
        labels = {
            'body': (''),
        }


class image_form(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['image']


class product_form(forms.ModelForm):
    requered_css_class = 'required-field'
    category = forms.ChoiceField(choices= CATEGORY_CHOICES)
    class Meta:
        model = Item
        fields = ['title', 'description', 'price', 'category', 'img']
        widgets = {
        'title': forms.TextInput(
            attrs={
                'placeholder': 'title',
                'rows': 1,
                'cols': 30,
                'class': 'item-form',
                'style': ''
                }),
        'description': forms.TextInput(
            attrs={
                'placeholder': 'description',
                'rows': 1,
                'cols': 20,
                'class': 'item-form',
                'style': ''
                }),
        'price': forms.TextInput(
            attrs={
                'placeholder': 'price',
                'rows': 1,
                'cols': 20,
                'class': 'item-form',
                'style': ''
                }),
        'category': forms.ChoiceField(
            label='',
            widget=forms.Select(attrs={'class':'category-form'})),
        'img': forms.FileInput(
            attrs={
                'style': '',
                'class': 'item-form'
                }),
        }


class edit_product_form(forms.ModelForm):
    requered_css_class = 'required-field'
    category = forms.ChoiceField(choices= CATEGORY_CHOICES)
    class Meta:
        model = Item
        fields = ['title', 'description', 'price', 'category', 'img']
        widgets = {
        'title': forms.TextInput(
            attrs={
                'placeholder': 'title',
                'rows': 1,
                'cols': 20,
                'class': 'item-form',
                'style': ''
                }),
        'description': forms.TextInput(
            attrs={
                'placeholder': 'description',
                'rows': 1,
                'cols': 20,
                'class': 'item-form',
                'style': ''
                }),
        'price': forms.TextInput(
            attrs={
                'placeholder': 'price',
                'rows': 1,
                'cols': 20,
                'class': 'item-form',
                'style': ''
                }),
        'category': forms.ChoiceField(
            label='',
            widget=forms.Select(attrs={'class':'category-form'})),
        'img': forms.FileInput(
            attrs={
                'style': '',
                'class': 'item-form'
                }),
        }
