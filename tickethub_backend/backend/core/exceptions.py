from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated, ValidationError
from rest_framework.views import exception_handler
from django.core.exceptions import ValidationError as ModelValidationError
from .errors import BusinessError
from django.db import IntegrityError


def api_exception_handler(exc, context):
    if isinstance(exc, IntegrityError):
        exc = BusinessError('INTEGRITY_CONFLICT', 'Данные уже изменились или запись существует. Обновите страницу.')
    if isinstance(exc, ModelValidationError):
        exc = ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)
    response = exception_handler(exc, context)
    if response is None:
        return None
    request = context.get("request")
    original = response.data
    code = {
        400: "VALIDATION_ERROR", 401: "AUTH_REQUIRED", 403: "FORBIDDEN",
        404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 415: "UNSUPPORTED_MEDIA_TYPE",
        429: "RATE_LIMITED",
    }.get(response.status_code, "API_ERROR")
    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        code = "AUTH_REQUIRED"
    if isinstance(exc, ValidationError):
        message = "Проверьте введённые данные."
        details = original
    else:
        message = str(original.get("detail", "Ошибка запроса.")) if isinstance(original, dict) else "Ошибка запроса."
        details = {}
    if isinstance(exc, BusinessError):
        code = exc.business_code
        details = exc.business_details
    response.data = {
        "code": code,
        "message": message,
        "details": details,
        "request_id": getattr(request, "request_id", None),
    }
    return response
