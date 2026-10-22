from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .api import payload
from .permissions import IsStaff, IsAdmin
from .serializers import StrictSerializer, StrictModelSerializer
from .staff import CatalogViewSet
from .models import ContentPage, PrivacyRequest, EmailLog
from . import content


def public_configuration():
    versions = dict(ContentPage.objects.filter(is_published=True, approved_by__isnull=False,
                    slug__in=settings.REQUIRED_LEGAL_SLUGS).values_list('slug', 'version'))
    legal_ready = not settings.REQUIRE_LEGAL_ACCEPTANCE or set(versions) == set(settings.REQUIRED_LEGAL_SLUGS)
    return {'currency': 'RUB', 'locales': ['ru', 'en'], 'public_forms_enabled': settings.PUBLIC_FORMS_ENABLED and legal_ready,
            'order_intake_enabled': settings.ORDER_INTAKE_ENABLED and settings.PUBLIC_FORMS_ENABLED and legal_ready,
            'checkout_mode': 'MANAGER', 'promo_codes_enabled': True, 'online_payments_enabled': False, 'ticket_download_enabled': False,
            'client_analytics_enabled': settings.CLIENT_ANALYTICS_ENABLED,
            'hold_seconds': settings.HOLD_SECONDS, 'direct_order_limit': settings.DIRECT_ORDER_LIMIT,
            'request_limit': settings.REQUEST_LIMIT, 'legal_versions': versions, 'legal_ready': legal_ready,
            'contacts': {'email': settings.CONTACT_EMAIL, 'phone': settings.CONTACT_PHONE, 'hours': settings.CONTACT_HOURS}}


class PublicConfig(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(public_configuration())


class PageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentPage
        fields = ['id', 'slug', 'version', 'title_ru', 'title_en', 'body_ru', 'body_en', 'published_at']


class PublicPage(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = PageSerializer
    lookup_field = 'slug'
    queryset = ContentPage.objects.filter(is_published=True, approved_by__isnull=False)


class StaffPageSerializer(StrictModelSerializer):
    class Meta:
        model = ContentPage
        fields = ['id', 'slug', 'version', 'title_ru', 'title_en', 'body_ru', 'body_en', 'published_at', 'is_published', 'approved_by']
        read_only_fields = ['id', 'published_at', 'is_published', 'approved_by']

    def create(self, validated_data):
        return content.save_page(None, validated_data)

    def update(self, instance, validated_data):
        return content.save_page(instance, validated_data)


class StaffPageViewSet(CatalogViewSet):
    permission_classes = [IsAdmin]
    queryset = ContentPage.objects.order_by('slug', '-version')
    serializer_class = StaffPageSerializer

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        payload(StrictSerializer, request)
        return Response(self.get_serializer(content.publish_page(self.get_object().pk, request.user)).data)


class CreatePrivacySerializer(StrictSerializer):
    kind = serializers.ChoiceField(choices=['ACCESS', 'CORRECT', 'DELETE'])
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class PrivacySerializer(serializers.ModelSerializer):
    class Meta:
        model = PrivacyRequest
        fields = ['id', 'kind', 'comment', 'status', 'response', 'created_at', 'updated_at']


class PrivacyList(generics.ListCreateAPIView):
    serializer_class = PrivacySerializer

    def get_queryset(self):
        return PrivacyRequest.objects.filter(user=self.request.user).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        from users.services import rate_limit, client_ip
        from .email import notify_staff
        rate_limit('privacy-request', request.user.email, client_ip(request), 5, 30, 86400)
        data = payload(CreatePrivacySerializer, request)
        obj = PrivacyRequest.objects.create(user=request.user, **data)
        notify_staff('Новый запрос по персональным данным', obj.id)
        return Response(self.get_serializer(obj).data, status=201)


class StaffPrivacySerializer(StrictModelSerializer):
    class Meta:
        model = PrivacyRequest
        fields = ['id', 'user', 'kind', 'comment', 'status', 'response', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'kind', 'comment', 'created_at', 'updated_at']


class StaffPrivacyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = StaffPrivacySerializer
    queryset = PrivacyRequest.objects.order_by('-created_at')

    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        obj = self.get_object()
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class EmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailLog
        fields = ['id', 'recipient', 'subject', 'body', 'status', 'attempts', 'sent_at', 'object_id', 'error_code', 'created_at', 'updated_at']


class StaffEmailViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = EmailSerializer
    queryset = EmailLog.objects.order_by('-created_at', 'id')

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        from .email import send_logged_email
        payload(StrictSerializer, request)
        obj = self.get_object()
        send_logged_email(obj.id)
        obj.refresh_from_db()
        return Response(self.get_serializer(obj).data)


class StaffSettings(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response({**public_configuration(), 'configuration_source': 'environment',
                         'require_legal_acceptance': settings.REQUIRE_LEGAL_ACCEPTANCE})
