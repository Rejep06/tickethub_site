from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from core.errors import BusinessError
from core.permissions import is_staff_session
from core.validation import clean_image, image_from_url


class StaffAdmin(admin.ModelAdmin):
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        from django.shortcuts import redirect
        from django.db import IntegrityError
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except (BusinessError, ValidationError, IntegrityError) as exc:
            text = 'Данные уже изменились. Обновите форму.' if isinstance(exc, IntegrityError) else str(exc)
            self.message_user(request, text, messages.ERROR)
            return redirect(request.path)

    def has_module_permission(self, request):
        return is_staff_session(request)

    def has_view_permission(self, request, obj=None):
        return is_staff_session(request)

    def has_add_permission(self, request):
        return is_staff_session(request)

    def has_change_permission(self, request, obj=None):
        return is_staff_session(request)

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyAdmin(StaffAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields] + [field.name for field in self.model._meta.many_to_many]


class VersionedAdminForm(forms.ModelForm):
    expected_version = forms.IntegerField(required=False, widget=forms.HiddenInput)

    class Meta:
        fields = '__all__'  # Admin only; API serializers always list allowed fields.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['expected_version'].initial = getattr(self.instance, 'version', None) if not self.instance._state.adding else None


class ImageAdminForm(VersionedAdminForm):
    image = forms.FileField(required=False, label='Изображение',
        widget=forms.ClearableFileInput(attrs={'accept': '.jpg,.jpeg,.png,.webp,.svg'}),
        help_text='PNG/JPEG/WebP: до 20 000 px по стороне, 300 МП, 100 МиБ. Статический SVG: до 10 МиБ.')
    image_url = forms.URLField(required=False, max_length=2000, label='Или ссылка на изображение',
        help_text='Прямая HTTPS-ссылка. Файл будет проверен и сохранён локально; поле не хранит ссылку вместо файла.')

    def clean(self):
        data = super().clean()
        uploaded = self.files.get('image')
        url = data.pop('image_url', '')
        if url and (uploaded or data.get('image') is False):
            self.add_error('image_url', 'Выберите либо файл, либо ссылку, без одновременного удаления.')
            return data
        if url and not self.errors:
            try:
                data['image'] = image_from_url(url)
            except ValidationError as exc:
                self.add_error('image_url', exc)
        elif uploaded and not self.errors:
            try:
                data['image'] = clean_image(uploaded)
            except ValidationError as exc:
                self.add_error('image', exc)
        return data


def run_action(admin_obj, request, queryset, operation):
    succeeded = 0
    for obj in queryset:
        try:
            operation(obj)
            succeeded += 1
        except (BusinessError, ValidationError) as exc:
            admin_obj.message_user(request, f'{obj}: {exc}', messages.ERROR)
    if succeeded:
        admin_obj.message_user(request, f'Выполнено операций: {succeeded}.', messages.SUCCESS)
