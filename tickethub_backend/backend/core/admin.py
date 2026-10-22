from django.contrib import admin
from .adminbase import StaffAdmin, ReadOnlyAdmin, run_action
from .models import ContentPage, ConsentRecord, PrivacyRequest, EmailLog
from .content import save_page, publish_page


@admin.register(ContentPage)
class ContentAdmin(StaffAdmin):
    list_display = ['slug', 'version', 'is_published', 'approved_by', 'published_at']
    readonly_fields = ['id', 'is_published', 'approved_by', 'published_at', 'created_at', 'updated_at']
    actions = ['publish']

    def has_add_permission(self, request):
        return super().has_add_permission(request) and request.user.staff_role == 'ADMIN'

    def has_change_permission(self, request, obj=None):
        return self.has_add_permission(request) and (obj is None or obj.published_at is None)

    def save_model(self, request, obj, form, change):
        saved = save_page(obj if change else None, dict(form.cleaned_data))
        obj.__dict__.update(saved.__dict__)

    @admin.action(description='Утвердить и опубликовать документ', permissions=['publish'])
    def publish(self, request, queryset):
        run_action(self, request, queryset, lambda obj: publish_page(obj.id, request.user))

    def has_publish_permission(self, request):
        return self.has_add_permission(request)


@admin.register(PrivacyRequest)
class PrivacyAdmin(StaffAdmin):
    list_display = ['id', 'user', 'kind', 'status', 'created_at']
    readonly_fields = ['id', 'user', 'kind', 'comment', 'created_at', 'updated_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and request.user.staff_role == 'ADMIN'


@admin.register(EmailLog)
class EmailAdmin(ReadOnlyAdmin):
    list_display = ['recipient', 'subject', 'status', 'attempts', 'sent_at']
    list_filter = ['status']
    actions = ['retry']

    @admin.action(description='Повторить неотправленные уведомления', permissions=['view'])
    def retry(self, request, queryset):
        from .email import send_logged_email
        run_action(self, request, queryset, lambda obj: send_logged_email(obj.id))


admin.site.register(ConsentRecord, ReadOnlyAdmin)
