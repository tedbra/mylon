from django import apps
from django.contrib.auth.forms import AuthenticationForm
from django import forms

class PremiumLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'placeholder': 'Enter your institutional username...',
        'style': 'width: 100%; box-sizing: border-box;'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Enter secret passphrase...',
        'style': 'width: 100%; box-sizing: border-box;'
    }))