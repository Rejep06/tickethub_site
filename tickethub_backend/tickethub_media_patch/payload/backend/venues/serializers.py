from rest_framework import serializers
from core.staff import CatalogSerializer
from core.serializers import StrictSerializer, StrictModelSerializer
from .models import Venue, SeatingPlan, Seat
from .services import save_plan, save_seat


class VenueSerializer(CatalogSerializer):
    class Meta:
        model = Venue
        fields = ['id', 'name_ru', 'name_en', 'country', 'city', 'city_en', 'address', 'address_en', 'timezone']
        read_only_fields = ['id']


class SeatSerializer(StrictModelSerializer):
    labels_known = serializers.BooleanField(read_only=True)
    sector = serializers.CharField(max_length=50)
    row = serializers.CharField(max_length=30)
    number = serializers.CharField(max_length=30)
    class Meta:
        model = Seat
        fields = ['id', 'plan', 'sector', 'row', 'number', 'x', 'y', 'adjacency_group', 'adjacency_position', 'labels_known', 'external_point_key']
        read_only_fields = ['id', 'labels_known', 'external_point_key']

    def create(self, validated_data):
        return save_seat(None, validated_data)

    def update(self, instance, validated_data):
        return save_seat(instance, validated_data)


class PlanSerializer(StrictModelSerializer):
    expected_version = serializers.IntegerField(write_only=True, required=False, min_value=1)

    class Meta:
        model = SeatingPlan
        fields = ['id', 'venue', 'name', 'image', 'rights_source', 'rights_confirmed', 'status', 'version',
                  'external_provider', 'external_layout_id', 'external_background_url',
                  'external_width', 'external_height', 'external_synced_at', 'expected_version']
        read_only_fields = ['id', 'image', 'status', 'version', 'external_provider', 'external_layout_id',
                            'external_background_url', 'external_width', 'external_height', 'external_synced_at']

    def create(self, validated_data):
        return save_plan(None, validated_data)

    def update(self, instance, validated_data):
        return save_plan(instance, validated_data)


class RowSerializer(StrictSerializer):
    sector = serializers.CharField(max_length=50)
    row = serializers.CharField(max_length=30)
    numbers = serializers.ListField(child=serializers.CharField(max_length=30), min_length=1, max_length=500)
    x1 = serializers.DecimalField(max_digits=7, decimal_places=6, min_value=0, max_value=1)
    y1 = serializers.DecimalField(max_digits=7, decimal_places=6, min_value=0, max_value=1)
    x2 = serializers.DecimalField(max_digits=7, decimal_places=6, min_value=0, max_value=1)
    y2 = serializers.DecimalField(max_digits=7, decimal_places=6, min_value=0, max_value=1)
    adjacency_group = serializers.CharField(max_length=80, required=False, allow_blank=True, default='')
