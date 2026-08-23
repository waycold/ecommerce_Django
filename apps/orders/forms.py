from django import forms
from apps.orders.models import Profile


class profile_edit_form(forms.ModelForm):
    birth_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = Profile
        fields = ['phone', 'description', 'address_line', 'city', 'province', 'zip_code', 'country', 'birth_date', 'gender']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'}),
            'address_line': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Street address, Apt, Suite'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}),
            'province': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State / Province / Region'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Postal Code'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Bio / Description'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
        }


class image_form(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['image']
