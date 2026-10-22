from django.contrib.auth.base_user import BaseUserManager
from django.core.validators import validate_email


class UserManager(BaseUserManager):
    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email):
        return super().normalize_email(email.strip()).lower() if email else ""

    def get_by_natural_key(self, email):
        return self.get(email__iexact=self.normalize_email(email))

    def create_user(self, email, password=None, **extra_fields):
        email = self.normalize_email(email)
        if not email:
            raise ValueError("Email is required.")
        validate_email(email)
        role = extra_fields.get("staff_role", "")
        if role not in {"", "MANAGER", "ADMIN"}:
            raise ValueError("Unsupported staff role.")
        if extra_fields.get("is_superuser", False) and role != "ADMIN":
            raise ValueError("A superuser must have the ADMIN role.")
        if role and not password:
            raise ValueError("Staff accounts require a password.")
        expected_staff = bool(role)
        if "is_staff" in extra_fields and extra_fields["is_staff"] != expected_staff:
            raise ValueError("is_staff must match staff_role.")
        extra_fields["is_staff"] = expected_staff
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("staff_role", "ADMIN")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if not extra_fields["is_superuser"] or not extra_fields["is_staff"]:
            raise ValueError("Superuser requires is_superuser=True and is_staff=True.")
        if not extra_fields["is_active"] or extra_fields["staff_role"] != "ADMIN":
            raise ValueError("Superuser must be active and have the ADMIN role.")
        return self.create_user(email, password, **extra_fields)
