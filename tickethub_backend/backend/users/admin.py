from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import AccountChangeForm, StaffUserCreationForm
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = AccountChangeForm
    add_form = StaffUserCreationForm
    list_display = ("email", "name", "staff_role", "is_active", "email_verified_at")
    list_filter = ("staff_role", "is_active", "locale")
    search_fields = ("email", "name", "phone")
    ordering = ("email",)
    readonly_fields = ("id", "date_joined", "last_login", "email_verified_at", "is_staff")
    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        ("Профиль", {"fields": ("name", "phone", "locale", "email_verified_at")}),
        ("Доступ", {"fields": ("staff_role", "is_staff", "is_active", "is_superuser", "groups", "user_permissions")}),
        ("История входа", {"fields": ("date_joined", "last_login")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "name", "staff_role", "password1", "password2")}),)


    def has_module_permission(self, request):
        from core.permissions import is_staff_session
        return is_staff_session(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request) and request.user.staff_role == 'ADMIN'

    def has_change_permission(self, request, obj=None):
        return self.has_add_permission(request) and (obj is None or not obj.is_superuser or request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request) and (obj is None or not obj.staff_role or request.user.staff_role == 'ADMIN')

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if request.user.staff_role == 'ADMIN' else qs.filter(staff_role='')

    def get_fieldsets(self, request, obj=None):
        fields = super().get_fieldsets(request, obj)
        if request.user.is_superuser:
            return fields
        return [(title, {**options, 'fields': tuple(field for field in options['fields']
                    if field not in (['is_superuser', 'groups', 'user_permissions'] + (['password'] if request.user.staff_role == 'MANAGER' else [])))}) for title, options in fields]


    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return (*fields, 'email') if obj else fields
