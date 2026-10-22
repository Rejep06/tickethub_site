from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from .models import User


class StaffUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "name", "staff_role")


class AccountChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"  # Server-side Django Admin form, never a customer serializer.
