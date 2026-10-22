from django.contrib import admin
from core.adminbase import StaffAdmin, ReadOnlyAdmin, VersionedAdminForm
from .models import PromoCode, PromoRedemption
from .services import save_promotion


@admin.register(PromoCode)
class PromoCodeAdmin(StaffAdmin):
    form = VersionedAdminForm
    list_display = ['code', 'kind', 'value', 'is_active', 'starts_at', 'ends_at', 'usage_limit']
    list_filter = ['is_active', 'kind']
    search_fields = ['code', 'description']
    readonly_fields = ['id', 'version', 'created_at', 'updated_at']

    def has_add_permission(self, request):
        return super().has_add_permission(request) and request.user.staff_role == 'ADMIN'

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and request.user.staff_role == 'ADMIN'

    def save_model(self, request, obj, form, change):
        saved = save_promotion(obj if change else None, dict(form.cleaned_data))
        obj.__dict__.update(saved.__dict__)


@admin.register(PromoRedemption)
class PromoRedemptionAdmin(ReadOnlyAdmin):
    list_display = ['code', 'order', 'discount_minor', 'created_at']
    search_fields = ['code', 'order__number']
