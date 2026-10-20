from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(label='Ваше имя', max_length=60)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'first_name')
