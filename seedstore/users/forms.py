from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class CustomUserCreationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="Password", min_length=6)
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirm Password", min_length=6)

    class Meta:
        model = User
        fields = ['email', 'password']  # Including only email and password fields for registration

    def clean_confirm_password(self):
        password = self.cleaned_data.get('password')
        confirm_password = self.cleaned_data.get('confirm_password')

        if password != confirm_password:
            raise ValidationError("Passwords do not match")

        return confirm_password