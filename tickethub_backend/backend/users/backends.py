from django.contrib.auth.backends import ModelBackend


class StaffPasswordBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(request, username=username, password=password, **kwargs)
        return user if user and user.is_staff and user.staff_role in {'ADMIN', 'MANAGER'} else None


class CustomerOTPBackend(ModelBackend):
    # Login is performed explicitly after a consumed OTP. Never authenticate a password here.
    def authenticate(self, request, **kwargs):
        return None
