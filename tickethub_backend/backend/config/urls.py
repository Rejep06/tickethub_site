from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from core.views import csrf_cookie, health_live, health_ready

admin.site.site_header = "Tickethub — управление"
admin.site.site_title = "Tickethub"
admin.site.index_title = "Каталог, заказы и обслуживание клиентов"

urlpatterns = [
    path("health/live/", health_live, name="health-live"),
    path("health/ready/", health_ready, name="health-ready"),
    path("api/v1/auth/csrf/", csrf_cookie, name="csrf-cookie"),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("users.urls")),
    path("api/v1/", include("venues.urls")),
    path("api/v1/", include("tickets.urls")),
    path("api/v1/", include("events.urls")),
    path("api/v1/", include("orders.urls")),
    path("api/v1/", include("promotions.urls")),
    path("api/v1/", include("ticket_requests.urls")),
    path("api/v1/", include("payments.urls")),
    path("api/v1/", include("analytics.urls")),
    path("api/v1/", include("external_events.urls")),
    path("ops/", admin.site.urls),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = "core.views.bad_request"
handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
