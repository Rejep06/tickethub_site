from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, mixins
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, JSONParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from core.api import payload
from core.serializers import ImageUploadSerializer, VersionActionSerializer, StrictSerializer
from core.staff import CatalogViewSet
from .models import Venue, SeatingPlan, Seat
from .serializers import VenueSerializer, PlanSerializer, SeatSerializer, RowSerializer
from . import services


class VenueList(generics.ListAPIView):
    permission_classes = [AllowAny]
    queryset = Venue.objects.order_by('name_ru', 'id')
    serializer_class = VenueSerializer


class StaffVenueViewSet(CatalogViewSet):
    queryset = Venue.objects.order_by('name_ru', 'id')
    serializer_class = VenueSerializer


class PlanImageSerializer(ImageUploadSerializer):
    expected_version = serializers.IntegerField(min_value=1)


class StaffPlanViewSet(CatalogViewSet):
    queryset = SeatingPlan.objects.order_by('-created_at', 'id')
    serializer_class = PlanSerializer

    @action(detail=True, methods=['post'], url_path='bulk-edit')
    def bulk_edit(self, request, pk=None):
        from .editor_api import bulk_edit
        return bulk_edit(request, self.get_object().pk)

    @action(detail=True, methods=['post'], url_path='block-preview')
    def block_preview(self, request, pk=None):
        from .editor_api import preview_block
        self.get_object()
        return preview_block(request)

    @action(detail=True, methods=['post'], url_path='csv-preview')
    def csv_preview(self, request, pk=None):
        from .editor_api import preview_csv
        self.get_object()
        return preview_csv(request)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        data = payload(VersionActionSerializer, request)
        return Response(self.get_serializer(services.publish_plan(self.get_object().pk, data['expected_version'])).data)

    @action(detail=True, methods=['post'], url_path='clone-version')
    def clone_version(self, request, pk=None):
        payload(StrictSerializer, request)
        return Response(self.get_serializer(services.clone_plan(self.get_object().pk)).data, status=201)

    @action(detail=True, methods=['get'])
    def seats(self, request, pk=None):
        plan = self.get_object()
        return Response(SeatSerializer(plan.seats.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='create-row')
    def create_row(self, request, pk=None):
        seats = services.create_row(self.get_object().pk, **payload(RowSerializer, request))
        return Response(SeatSerializer(seats, many=True).data, status=201)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, JSONParser, FormParser])
    def image(self, request, pk=None):
        obj = services.save_plan(self.get_object(), payload(PlanImageSerializer, request))
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        obj = self.get_object()
        plan = dict(self.get_serializer(obj).data)
        # Large imported geometry is returned only by preview, not every plan list response.
        plan['external_geometry'] = obj.external_geometry
        plan['external_sectors'] = obj.external_sectors
        plan['total_seats'] = obj.seats.count()
        plan['labels_unknown'] = obj.seats.filter(sector='', row='', number='').count()
        return Response({'plan': plan, 'seats': SeatSerializer(obj.seats.all(), many=True).data})


class StaffSeatViewSet(mixins.DestroyModelMixin, CatalogViewSet):
    queryset = Seat.objects.all()
    serializer_class = SeatSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def perform_destroy(self, instance):
        services.delete_seat(instance.pk)

    def get_queryset(self):
        queryset = super().get_queryset()
        if 'plan' in self.request.query_params:
            field = serializers.UUIDField()
            queryset = queryset.filter(plan_id=field.run_validation(self.request.query_params['plan']))
        return queryset
