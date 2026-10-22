import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractUser):
    class StaffRole(models.TextChoices):
        MANAGER = "MANAGER", "Менеджер"
        ADMIN = "ADMIN", "Администратор"

    username = None
    first_name = None
    last_name = None
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("email", unique=True)
    name = models.CharField("имя", max_length=100, blank=True)
    phone = models.CharField("телефон", max_length=16, blank=True)
    locale = models.CharField("язык", max_length=2, choices=[("ru", "Русский"), ("en", "English")], default="ru")
    email_verified_at = models.DateTimeField("email подтверждён", null=True, blank=True)
    staff_role = models.CharField("роль сотрудника", max_length=7, choices=StaffRole.choices, blank=True, default="")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        constraints = [
            models.UniqueConstraint(Lower("email"), name="users_email_case_insensitive_unique"),
            models.CheckConstraint(
                condition=(models.Q(staff_role="", is_staff=False) | models.Q(staff_role__in=["ADMIN", "MANAGER"], is_staff=True)),
                name="users_staff_role_matches_flag",
            ),
            models.CheckConstraint(
                condition=models.Q(is_superuser=False) | models.Q(staff_role="ADMIN", is_staff=True),
                name="users_superuser_requires_admin",
            ),
        ]

    def clean(self):
        super().clean()
        self.email = UserManager.normalize_email(self.email)
        self.is_staff = bool(self.staff_role)
        if self.is_superuser and self.staff_role != self.StaffRole.ADMIN:
            raise ValidationError({"staff_role": "Суперпользователь должен иметь роль ADMIN."})

    def save(self, *args, **kwargs):
        self.email = UserManager.normalize_email(self.email)
        self.is_staff = bool(self.staff_role)
        # Keep a role update and its derived Django flag in the same UPDATE.
        if kwargs.get("update_fields") is not None and "staff_role" in kwargs["update_fields"]:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"is_staff"}
        super().save(*args, **kwargs)

    def get_full_name(self):
        return self.name.strip()

    def get_short_name(self):
        return self.name.strip() or self.email

    def __str__(self):
        return self.email


class AuthChallenge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    purpose = models.CharField(max_length=80, default='login')
    nonce = models.UUIDField(default=uuid.uuid4)
    code_hmac = models.CharField(max_length=64, blank=True)
    issued_at = models.DateTimeField(null=True)
    expires_at = models.DateTimeField(null=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['email', 'purpose'], name='otp_email_purpose_unique')]


class AuthRateLimit(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    window_start = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)
