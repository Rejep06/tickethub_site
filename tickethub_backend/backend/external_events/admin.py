from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.urls import path, reverse
from core.adminbase import ReadOnlyAdmin, StaffAdmin
from core.permissions import is_staff_session
from .models import (
    ExternalEvent, ExternalDate, ExternalSnapshot,
    ExternalSeatInventory, ExternalStandingInventory,
)


class ImportAdmin(ReadOnlyAdmin):
    def has_module_permission(self, request):
        return is_staff_session(request) and request.user.staff_role == 'ADMIN'

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)


class DatesInline(admin.TabularInline):
    model = ExternalDate
    extra = 0
    can_delete = False
    fields = ['external_date_id', 'event', 'source_active', 'source_start_at', 'last_seen_at']
    readonly_fields = fields
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ExternalEvent)
class ExternalEventAdmin(ImportAdmin):
    list_display = ['title', 'external_event_id', 'status', 'last_metadata_sync_at']
    search_fields = ['title', 'external_event_id', 'url']
    list_filter = ['status']
    inlines = [DatesInline]
    change_list_template = 'admin/external_events/change_list.html'

    def get_urls(self):
        return [path('import-url/', self.admin_site.admin_view(self.import_page), name='external_events_import_url')] + super().get_urls()

    def import_page(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        config = {
            'preview_url': reverse('staff-external-events-preview'),
            'import_url': reverse('staff-external-events-import-event'),
            'source_base': reverse('staff-external-events-list'),
            'event_admin_base': reverse('admin:events_event_changelist'),
            'plans_admin': reverse('admin:venues_seatingplan_changelist'),
        }
        return TemplateResponse(request, 'admin/external_events/import.html', {
            **self.admin_site.each_context(request), 'title': 'Импорт PortalBilet',
            'opts': self.model._meta, 'import_config': config,
        })


@admin.register(ExternalSnapshot)
class ExternalSnapshotAdmin(ImportAdmin):
    list_display = ['external_event', 'resource', 'byte_count', 'updated_at']
    list_filter = ['resource']
    search_fields = ['external_event__title', 'resource']


class InventoryAdmin(StaffAdmin):
    """Only the local enabled_for_sale decision is editable; provider fields stay read-only."""
    actions = ['enable_selected', 'disable_selected']

    def has_module_permission(self, request):
        return is_staff_session(request) and request.user.staff_role == 'ADMIN'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='Разрешить выбранное для локальной продажи')
    def enable_selected(self, request, queryset):
        queryset.update(enabled_for_sale=True)

    @admin.action(description='Запретить выбранное для локальной продажи')
    def disable_selected(self, request, queryset):
        queryset.update(enabled_for_sale=False)


@admin.register(ExternalSeatInventory)
class ExternalSeatInventoryAdmin(InventoryAdmin):
    list_display = ['external_date', 'seat', 'source_price_minor', 'source_available', 'enabled_for_sale', 'last_seen_at']
    list_filter = ['source_available', 'enabled_for_sale', 'external_date__external_event', 'seat__sector', 'seat__row']
    search_fields = ['seat__sector', 'seat__row', 'seat__number', 'external_ticket_id']
    readonly_fields = ['external_date', 'seat', 'external_ticket_id', 'source_price_minor', 'currency',
                       'source_code', 'source_available', 'last_seen_at', 'created_at', 'updated_at']


@admin.register(ExternalStandingInventory)
class ExternalStandingInventoryAdmin(InventoryAdmin):
    list_display = ['external_date', 'name', 'source_price_minor', 'available_count', 'source_available', 'enabled_for_sale']
    list_filter = ['source_available', 'enabled_for_sale', 'external_date__external_event']
    search_fields = ['name', 'external_ticket_id']
    readonly_fields = ['external_date', 'external_key', 'name', 'external_ticket_id', 'source_price_minor', 'currency',
                       'source_code', 'available_count', 'source_available', 'last_seen_at', 'created_at', 'updated_at']
