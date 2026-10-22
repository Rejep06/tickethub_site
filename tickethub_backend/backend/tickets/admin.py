from django.contrib import admin
from core.adminbase import StaffAdmin, ReadOnlyAdmin, VersionedAdminForm
from .models import Supplier, TicketOffer, TicketUnit, CheckoutHold, CheckoutHoldItem
from . import services


@admin.register(Supplier)
class SupplierAdmin(StaffAdmin):
    list_display = ['name', 'contact', 'is_active']
    search_fields = ['name', 'contact']


@admin.register(TicketOffer)
class OfferAdmin(StaffAdmin):
    form = VersionedAdminForm
    list_display = ['name_ru', 'event', 'mode', 'sale_price_minor', 'is_active']
    list_filter = ['event', 'mode']
    readonly_fields = ['id', 'version', 'created_at', 'updated_at']

    def save_model(self, request, obj, form, change):
        saved = services.save_offer(obj if change else None, dict(form.cleaned_data))
        obj.__dict__.update(saved.__dict__)


@admin.register(TicketUnit)
class UnitAdmin(StaffAdmin):
    form = VersionedAdminForm
    list_display = ['id', 'event', 'offer', 'seat', 'status', 'purchase_price_minor', 'supplier']
    list_filter = ['event', 'status', 'supplier']
    search_fields = ['supplier_reference', 'offer__name_ru']
    readonly_fields = ['id', 'status', 'current_hold', 'version', 'created_at', 'updated_at']

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (obj is None or obj.status in ['AVAILABLE', 'BLOCKED'])

    def save_model(self, request, obj, form, change):
        saved = services.save_unit(obj if change else None, dict(form.cleaned_data))
        obj.__dict__.update(saved.__dict__)


@admin.register(CheckoutHold)
class HoldAdmin(ReadOnlyAdmin):
    list_display = ['id', 'user', 'event', 'status', 'expires_at']
    list_filter = ['status']


admin.site.register(CheckoutHoldItem, ReadOnlyAdmin)
