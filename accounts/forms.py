from django.contrib.auth import get_user_model
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm

User = get_user_model()


class CustomUserCreationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("phone",)


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = (
            "phone",
            "first_name",
            "last_name",
            "email",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
        )