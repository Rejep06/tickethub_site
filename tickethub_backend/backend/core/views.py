import logging

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ApiInfoSerializer

logger = logging.getLogger(__name__)


class ApiInfoView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(responses=ApiInfoSerializer, auth=[], tags=["foundation"])
    def get(self, request):
        from .public_api import public_configuration
        return Response({
            "name": "Tickethub API",
            "version": "v1",
            "implementation_stage": "BACKEND_MVP",
            "order_intake_enabled": public_configuration()["order_intake_enabled"],
            "online_payments_enabled": False,
        })


@require_GET
def health_live(request):
    return JsonResponse({"status": "ok"})


@require_GET
def health_ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        # No database credentials or driver error details in public responses/logs.
        logger.warning("Database readiness check failed")
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


@require_GET
@ensure_csrf_cookie
def csrf_cookie(request):
    return JsonResponse({"csrf_token": get_token(request)})


def error_response(request, status, code, message):
    return JsonResponse({
        "code": code, "message": message, "details": {},
        "request_id": getattr(request, "request_id", None),
    }, status=status)


def csrf_failure(request, reason=""):
    return error_response(request, 403, "CSRF_FAILED", "Обновите страницу и повторите запрос.")


def bad_request(request, exception):
    return error_response(request, 400, "BAD_REQUEST", "Некорректный запрос.")


def not_found(request, exception):
    return error_response(request, 404, "NOT_FOUND", "Ресурс не найден.")


def server_error(request):
    return error_response(request, 500, "INTERNAL_ERROR", "Внутренняя ошибка сервера.")
