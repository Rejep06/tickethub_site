# Explicit initial migration, written before Django became available.
# Must be compared with `makemigrations --check --dry-run` before applying.
import uuid
import django.utils.timezone
from django.db import migrations, models
import django.db.models.functions.text
import users.managers


class Migration(migrations.Migration):
    initial = True
    dependencies = [("auth", "0012_alter_user_first_name_max_length")]
    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False, help_text="Designates that this user has all permissions without explicitly assigning them.", verbose_name="superuser status")),
                ("is_staff", models.BooleanField(default=False, help_text="Designates whether the user can log into this admin site.", verbose_name="staff status")),
                ("is_active", models.BooleanField(default=True, help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.", verbose_name="active")),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now, verbose_name="date joined")),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=254, unique=True, verbose_name="email")),
                ("name", models.CharField(blank=True, max_length=100, verbose_name="имя")),
                ("phone", models.CharField(blank=True, max_length=16, verbose_name="телефон")),
                ("locale", models.CharField(choices=[("ru", "Русский"), ("en", "English")], default="ru", max_length=2, verbose_name="язык")),
                ("email_verified_at", models.DateTimeField(blank=True, null=True, verbose_name="email подтверждён")),
                ("staff_role", models.CharField(blank=True, choices=[("MANAGER", "Менеджер"), ("ADMIN", "Администратор")], default="", max_length=7, verbose_name="роль сотрудника")),
                ("groups", models.ManyToManyField(blank=True, help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.", related_name="user_set", related_query_name="user", to="auth.group", verbose_name="groups")),
                ("user_permissions", models.ManyToManyField(blank=True, help_text="Specific permissions for this user.", related_name="user_set", related_query_name="user", to="auth.permission", verbose_name="user permissions")),
            ],
            options={
                "verbose_name": "user",
                "verbose_name_plural": "users",
                "constraints": [
                    models.UniqueConstraint(django.db.models.functions.text.Lower("email"), name="users_email_case_insensitive_unique"),
                    models.CheckConstraint(condition=models.Q(staff_role="", is_staff=False) | models.Q(staff_role__in=["ADMIN", "MANAGER"], is_staff=True), name="users_staff_role_matches_flag"),
                    models.CheckConstraint(condition=models.Q(is_superuser=False) | models.Q(staff_role="ADMIN", is_staff=True), name="users_superuser_requires_admin"),
                ],
            },
            managers=[("objects", users.managers.UserManager())],
        ),
    ]
