from rest_framework.permissions import BasePermission
from django.contrib.auth import BACKEND_SESSION_KEY


def is_staff_session(request):
    user = request.user
    return bool(user.is_authenticated and user.is_active and user.is_staff
                and user.staff_role in {'ADMIN', 'MANAGER'}
                and request.session.get(BACKEND_SESSION_KEY) == 'users.backends.StaffPasswordBackend')


class IsStaff(BasePermission):
    message = 'Требуется вход сотрудника по паролю.'

    def has_permission(self, request, view):
        return is_staff_session(request)


class IsAdmin(IsStaff):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.staff_role == 'ADMIN'
