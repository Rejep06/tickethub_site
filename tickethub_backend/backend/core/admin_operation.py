from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from core.errors import BusinessError
from rest_framework.exceptions import ValidationError as APIValidationError


def operation_page(model_admin, request, obj, title, form_class, execute, initial=None, form_kwargs=None):
    if obj is None:
        raise Http404
    form = form_class(request.POST if request.method == 'POST' else None, initial=initial or {}, **(form_kwargs or {}))
    if request.method == 'POST' and form.is_valid():
        try:
            execute(dict(form.cleaned_data))
        except (BusinessError, ValidationError, APIValidationError) as exc:
            form.add_error(None, str(exc))
        else:
            model_admin.message_user(request, 'Операция сохранена.', messages.SUCCESS)
            return redirect(reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_change', args=[obj.pk]))
    context = {**model_admin.admin_site.each_context(request), 'title': title, 'form': form, 'object': obj,
               'opts': obj._meta, 'media': model_admin.media + form.media}
    return TemplateResponse(request, 'admin/tickethub_operation.html', context)
