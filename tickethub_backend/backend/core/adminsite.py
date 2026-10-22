from django.contrib.admin import AdminSite
from core.permissions import is_staff_session


class TickethubAdminSite(AdminSite):
    site_header = 'Tickethub — управление'
    site_title = 'Tickethub'
    index_title = 'Каталог и обслуживание заказов'

    def has_permission(self, request):
        return is_staff_session(request)

    def login(self, request, extra_context=None):
        if request.method == 'POST':
            from users.services import rate_limit, client_ip
            from core.errors import BusinessError
            from core.views import error_response
            try:
                rate_limit('staff-login', request.POST.get('username', '').strip().lower(), client_ip(request), 15, 60)
            except BusinessError as exc:
                return error_response(request, exc.status_code, exc.business_code, str(exc.detail))
        return super().login(request, extra_context)
