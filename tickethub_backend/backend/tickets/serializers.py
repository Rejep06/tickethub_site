from django.utils import timezone
from rest_framework import serializers
from core.serializers import StrictSerializer, StrictModelSerializer
from core.staff import CatalogSerializer
from .models import Supplier, TicketOffer, TicketUnit, CheckoutHold, CheckoutHoldItem
from . import services


class SupplierSerializer(CatalogSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'contact', 'notes', 'is_active']
        read_only_fields = ['id']


class OfferSerializer(serializers.ModelSerializer):
    available_count = serializers.SerializerMethodField()

    class Meta:
        model = TicketOffer
        fields = ['id', 'event', 'name_ru', 'name_en', 'description_ru', 'description_en', 'kind', 'mode',
                  'sale_price_minor', 'available_count', 'version']

    def get_available_count(self, obj):
        if hasattr(obj, 'available_count_value'):
            return obj.available_count_value
        return services.available_units(obj.event).filter(offer=obj).count()


class StaffOfferSerializer(StrictModelSerializer):
    expected_version = serializers.IntegerField(write_only=True, required=False, min_value=1)

    class Meta:
        model = TicketOffer
        fields = ['id', 'event', 'name_ru', 'name_en', 'description_ru', 'description_en', 'sale_price_minor',
                  'kind', 'mode', 'is_active', 'version', 'expected_version']
        read_only_fields = ['id', 'version']

    def create(self, validated_data):
        return services.save_offer(None, validated_data)

    def update(self, instance, validated_data):
        return services.save_offer(instance, validated_data)


class StaffUnitSerializer(StrictModelSerializer):
    expected_version = serializers.IntegerField(write_only=True, required=False, min_value=1)

    class Meta:
        model = TicketUnit
        fields = ['id', 'event', 'offer', 'seat', 'supplier', 'purchase_price_minor', 'supplier_reference',
                  'stock_basis', 'allocation_until', 'status', 'internal_notes', 'version', 'expected_version']
        read_only_fields = ['id', 'status', 'version']
        # Cross-field validation runs under the event lock in save_unit.
        validators = []

    def create(self, validated_data):
        return services.save_unit(None, validated_data)

    def update(self, instance, validated_data):
        return services.save_unit(instance, validated_data)


class SelectionSerializer(StrictSerializer):
    mode = serializers.ChoiceField(choices=['SEATS', 'CATEGORY'])
    seat_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=10, required=False)
    offer_id = serializers.UUIDField(required=False)
    quantity = serializers.IntegerField(min_value=1, max_value=10, required=False)

    def validate(self, attrs):
        if attrs['mode'] == 'SEATS':
            if 'seat_ids' not in attrs or 'offer_id' in attrs or 'quantity' in attrs:
                raise serializers.ValidationError('Для SEATS нужны только seat_ids.')
            if len(set(attrs['seat_ids'])) != len(attrs['seat_ids']):
                raise serializers.ValidationError('Места повторяются.')
        elif 'offer_id' not in attrs or 'quantity' not in attrs or 'seat_ids' in attrs:
            raise serializers.ValidationError('Для CATEGORY нужны offer_id и quantity.')
        return attrs


class PreviewSerializer(StrictSerializer):
    event_id = serializers.UUIDField()
    selection = SelectionSerializer()


class CreateHoldSerializer(PreviewSerializer):
    expected_total_minor = serializers.IntegerField(min_value=1)
    expected_offer_versions = serializers.DictField(child=serializers.IntegerField(min_value=1), required=False)


class HoldItemSerializer(serializers.ModelSerializer):
    seat_id = serializers.UUIDField(source='ticket_unit.seat_id', read_only=True, allow_null=True)
    offer_id = serializers.UUIDField(source='ticket_unit.offer_id', read_only=True)

    class Meta:
        model = CheckoutHoldItem
        fields = ['id', 'offer_id', 'seat_id', 'name_ru', 'name_en', 'sector', 'row', 'seat_number', 'sale_price_minor']


class HoldSerializer(serializers.ModelSerializer):
    items = HoldItemSerializer(many=True, read_only=True)
    server_now = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    order_id = serializers.SerializerMethodField()

    class Meta:
        model = CheckoutHold
        fields = ['id', 'event', 'quote', 'status', 'expires_at', 'server_now', 'total_minor', 'currency', 'items', 'order_id']

    def get_server_now(self, obj):
        return timezone.now()

    def get_status(self, obj):
        return 'EXPIRED' if obj.status == 'ACTIVE' and obj.expires_at <= timezone.now() else obj.status

    def get_currency(self, obj):
        return 'RUB'

    def get_order_id(self, obj):
        if obj.status != 'CONVERTED':
            return None
        from orders.models import Order
        return Order.objects.filter(hold=obj).values_list('pk', flat=True).first()
