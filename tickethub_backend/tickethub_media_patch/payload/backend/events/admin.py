from django.contrib import admin
from core.adminbase import StaffAdmin, ImageAdminForm
from .models import Category, Participant, Event
from .services import save_event


@admin.register(Category)
class CategoryAdmin(StaffAdmin):
    list_display = ['name_ru', 'kind', 'parent', 'is_active']
    list_filter = ['kind', 'is_active']
    search_fields = ['name_ru', 'name_en']
    prepopulated_fields = {'slug': ['name_en']}


@admin.register(Participant)
class ParticipantAdmin(StaffAdmin):
    list_display = ['name_ru', 'kind']
    search_fields = ['name_ru', 'name_en']


@admin.register(Event)
class EventAdmin(StaffAdmin):
    form = ImageAdminForm
    list_display = ['title_ru', 'start_at', 'status', 'visibility', 'is_published']
    list_filter = ['status', 'is_published', 'category']
    search_fields = ['title_ru', 'title_en', 'slug']
    readonly_fields = ['id', 'version', 'created_at', 'updated_at']
    filter_horizontal = ['participants']
    prepopulated_fields = {'slug': ['title_en']}

    def save_model(self, request, obj, form, change):
        data = {key: value for key, value in form.cleaned_data.items() if key not in ['participants']}
        saved = save_event(obj if change else None, data, request.user)
        obj.__dict__.update(saved.__dict__)
