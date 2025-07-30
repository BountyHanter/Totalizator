from django import forms
from django.contrib.auth.forms import UserCreationForm as DjangoUserCreationForm
from django.contrib.auth import get_user_model

class UserCreationForm(DjangoUserCreationForm):
    """
    Форма регистрации, привязанная к модели CustomUser.
    """
    class Meta(DjangoUserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "password1", "password2")