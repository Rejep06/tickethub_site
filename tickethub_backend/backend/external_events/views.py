from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from core.api import payload
from core.permissions import IsAdmin
from core.serializers import StrictSerializer
from core.errors import BusinessError
from .http import ProviderError
from .models import ExternalEvent
from .serializers import ImportSerializer, SourceSerializer
from . import services


def provider_call(operation):
    try:
        return operation()
    except ProviderError as exc:
        status = 400 if exc.code in {'INVALID_PORTALBILET_URL', 'UNSAFE_URL'} else 502
        raise BusinessError(exc.code, str(exc), status=status) from exc


class ExternalEventViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = SourceSerializer
    queryset = ExternalEvent.objects.prefetch_related('dates').order_by('-updated_at', 'id')
    http_method_names = ['get', 'post', 'head', 'options']

    @action(detail=False, methods=['post'], url_path='preview')
    def preview(self, request):
        data = payload(ImportSerializer, request)
        return Response(provider_call(lambda: services.inspect_url(data['url'])))

    @action(detail=False, methods=['post'], url_path='import')
    def import_event(self, request):
        data = payload(ImportSerializer, request)
        operation = (lambda: services.inspect_url(data['url'])) if data['preview'] else (
            lambda: services.import_url(data['url'], request.user))
        # 200 reports a processed request, not a completed import. Inspect status.
        return Response(provider_call(operation))

    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        payload(StrictSerializer, request)
        source = self.get_object()
        return Response(provider_call(lambda: services.sync_source(source.pk, request.user)))
