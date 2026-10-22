from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, JSONParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from core.api import payload
from core.serializers import ImageUploadSerializer, VersionActionSerializer, StrictSerializer
from core.staff import CatalogViewSet
from .models import Category, Participant, Event
from .serializers import CategorySerializer, ParticipantSerializer, EventSerializer, StaffEventSerializer
from .services import public_events, save_event


class EventFilterSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, max_length=200)
    category = serializers.UUIDField(required=False)
    venue = serializers.UUIDField(required=False)
    participant = serializers.UUIDField(required=False)
    city = serializers.CharField(required=False, max_length=100)
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    status = serializers.ChoiceField(choices=['SCHEDULED', 'POSTPONED', 'CANCELLED', 'FINISHED'], required=False)
    ordering = serializers.ChoiceField(choices=['start_at', '-start_at', 'created_at', '-created_at'], default='start_at')


def filtered_events(queryset, parameters):
    serializer = EventFilterSerializer(data=parameters)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if data.get('q'):
        queryset = queryset.filter(Q(title_ru__icontains=data['q']) | Q(title_en__icontains=data['q']))
    for key in ['category', 'venue']:
        if key in data:
            queryset = queryset.filter(**{key + '_id': data[key]})
    if 'participant' in data:
        queryset = queryset.filter(participants__id=data['participant'])
    if 'city' in data:
        queryset = queryset.filter(venue__city__iexact=data['city'])
    if 'date_from' in data:
        queryset = queryset.filter(start_at__gte=data['date_from'])
    if 'date_to' in data:
        queryset = queryset.filter(start_at__lt=data['date_to'])
    if 'status' in data:
        queryset = queryset.filter(status=data['status'])
    return queryset.order_by(data['ordering'], 'id')


class CategoryList(generics.ListAPIView):
    permission_classes = [AllowAny]
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer


class ParticipantList(generics.ListAPIView):
    permission_classes = [AllowAny]
    queryset = Participant.objects.order_by('name_ru', 'id')
    serializer_class = ParticipantSerializer


class EventList(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = EventSerializer

    def get_queryset(self):
        return filtered_events(public_events(), self.request.query_params)


class EventDetail(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = EventSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return public_events()


class StaffCategoryViewSet(CatalogViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class StaffParticipantViewSet(CatalogViewSet):
    queryset = Participant.objects.order_by('name_ru', 'id')
    serializer_class = ParticipantSerializer


class StaffEventViewSet(CatalogViewSet):
    serializer_class = StaffEventSerializer
    queryset = Event.objects.select_related('venue', 'category').prefetch_related('participants')

    def get_queryset(self):
        return filtered_events(super().get_queryset(), self.request.query_params)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        data = payload(VersionActionSerializer, request)
        data.pop('reason', None)
        obj = save_event(self.get_object(), {**data, 'is_published': True}, request.user)
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'])
    def unpublish(self, request, pk=None):
        data = payload(VersionActionSerializer, request)
        data.pop('reason', None)
        obj = save_event(self.get_object(), {**data, 'is_published': False}, request.user)
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, JSONParser, FormParser])
    def image(self, request, pk=None):
        data = payload(EventImageSerializer, request)
        obj = save_event(self.get_object(), {'expected_version': data['expected_version'], 'image': data['image'],
                                            'image_rights_source': data['rights_source'],
                                            'image_rights_confirmed': data['rights_confirmed']}, request.user)
        return Response(self.get_serializer(obj).data)


class EventImageSerializer(ImageUploadSerializer):
    expected_version = serializers.IntegerField(min_value=1)
