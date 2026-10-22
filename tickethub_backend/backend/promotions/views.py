from django.db.models import Count
from rest_framework.response import Response
from rest_framework.views import APIView
from core.api import payload
from core.permissions import IsStaff, IsAdmin
from core.staff import CatalogViewSet
from users.services import rate_limit, client_ip
from .models import PromoCode
from .serializers import PromoCodeSerializer, PromoPreviewSerializer
from .services import preview_promotion


class PromoPreview(APIView):
    serializer_class = PromoPreviewSerializer

    def post(self, request):
        rate_limit('promo-preview', request.user.email, client_ip(request), 30, 150, 600)
        data = payload(PromoPreviewSerializer, request)
        return Response(preview_promotion(request.user, data['hold_id'], data['code']))


class StaffPromoCodeViewSet(CatalogViewSet):
    serializer_class = PromoCodeSerializer
    queryset = PromoCode.objects.annotate(usage_count=Count('redemptions')).order_by('-created_at', 'id')

    def get_permissions(self):
        return [IsStaff() if self.request.method in {'GET', 'HEAD', 'OPTIONS'} else IsAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('q'):
            qs = qs.filter(code__icontains=self.request.query_params['q'][:40])
        return qs
