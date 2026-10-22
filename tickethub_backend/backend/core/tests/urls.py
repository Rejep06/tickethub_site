from django.urls import include, path
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class PrivateProbe(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({"ok": True})


urlpatterns = [
    path("api/v1/test-private/", PrivateProbe.as_view()),
    path("", include("config.urls")),
]
handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
