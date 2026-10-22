from django.contrib import admin
from django.urls import path, reverse
from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404
from django.utils.html import format_html
from core.adminbase import StaffAdmin, ImageAdminForm, run_action
from .models import Venue, SeatingPlan, Seat
from . import services


@admin.register(Venue)
class VenueAdmin(StaffAdmin):
    list_display = ['name_ru', 'city', 'country', 'timezone']
    search_fields = ['name_ru', 'city']


@admin.register(SeatingPlan)
class PlanAdmin(StaffAdmin):
    form = ImageAdminForm
    list_display = ['name', 'venue', 'status', 'version', 'external_provider', 'external_layout_id', 'editor_link']
    change_form_template = 'admin/venues/plan_change_form.html'
    readonly_fields = ['id', 'status', 'version', 'created_at', 'updated_at']
    actions = ['publish', 'clone']

    def get_urls(self):
        return [path('<uuid:object_id>/editor/', self.admin_site.admin_view(self.editor),
                     name='venues_seatingplan_editor')] + super().get_urls()

    @admin.display(description='Схема')
    def editor_link(self, obj):
        return format_html('<a href="{}">Открыть редактор</a>',
                           reverse('admin:venues_seatingplan_editor', args=[obj.pk]))

    def editor(self, request, object_id):
        plan = get_object_or_404(SeatingPlan, pk=object_id)
        context = {**self.admin_site.each_context(request), 'opts': self.model._meta,
                   'title': 'Редактор схемы — ' + plan.name, 'plan': plan,
                   'editor_config': {
                       'api': reverse('staff-plans-detail', args=[plan.pk]),
                       'editor_base': reverse('admin:venues_seatingplan_changelist'),
                       'change_url': reverse('admin:venues_seatingplan_change', args=[plan.pk]),
                   }}
        return TemplateResponse(request, 'admin/venues/editor.html', context)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (obj is None or obj.status == 'DRAFT')

    def save_model(self, request, obj, form, change):
        saved = services.save_plan(obj if change else None, dict(form.cleaned_data))
        obj.__dict__.update(saved.__dict__)

    @admin.action(description='Опубликовать черновик схемы', permissions=['view'])
    def publish(self, request, queryset):
        run_action(self, request, queryset, lambda obj: services.publish_plan(obj.id, obj.version))

    @admin.action(description='Клонировать в новый черновик', permissions=['view'])
    def clone(self, request, queryset):
        run_action(self, request, queryset, lambda obj: services.clone_plan(obj.id))


@admin.register(Seat)
class SeatAdmin(StaffAdmin):
    list_display = ['plan', 'sector', 'row', 'number', 'labels_known', 'x', 'y']
    list_filter = ['plan', 'sector']
    readonly_fields = ['id', 'created_at', 'updated_at']

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (obj is None or (obj.plan.status == 'DRAFT' and not obj.external_point_key))

    def has_delete_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (obj is None or (obj.plan.status == 'DRAFT' and not obj.external_point_key and not obj.units.exists()))

    def save_model(self, request, obj, form, change):
        saved = services.save_seat(obj if change else None, dict(form.cleaned_data))
        obj.__dict__.update(saved.__dict__)

    def delete_model(self, request, obj):
        services.delete_seat(obj.pk)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            services.delete_seat(obj.pk)
