from rest_framework import serializers
from core.serializers import StrictSerializer, VersionActionSerializer
from payments.selectors import money_summary, sent_summary
from .models import Order, OrderItem, OrderHistory, CustomerCase, DeliveryRecord


class CreateOrderSerializer(StrictSerializer):
    hold_id = serializers.UUIDField()
    fan_id_answer = serializers.ChoiceField(choices=['HAS_FAN_ID', 'NEEDS_HELP', 'NOT_SURE'], required=False)
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    accepted_documents = serializers.DictField(child=serializers.IntegerField(min_value=1), required=False, default=dict)
    promo_code = serializers.CharField(max_length=40, required=False, allow_blank=True)
    expected_total_minor = serializers.IntegerField(min_value=1, required=False)
    expected_discount_minor = serializers.IntegerField(min_value=0, required=False)
    expected_promo_version = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        if attrs.get('promo_code'):
            for name in ['expected_total_minor', 'expected_discount_minor', 'expected_promo_version']:
                if name not in attrs:
                    raise serializers.ValidationError({name: 'Сначала примените промокод и подтвердите сумму.'})
        elif 'expected_promo_version' in attrs or attrs.get('expected_discount_minor', 0) != 0:
            raise serializers.ValidationError({'promo_code': 'Укажите промокод для скидки.'})
        return attrs


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'name_ru', 'name_en', 'sector', 'row', 'seat_number', 'original_price_minor', 'discount_minor', 'sale_price_minor', 'is_active']


class OrderHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderHistory
        fields = ['id', 'event_type', 'public_message', 'created_at']


class CaseSerializer(serializers.ModelSerializer):
    items = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = CustomerCase
        fields = ['id', 'order', 'kind', 'items', 'reason', 'requested_minor', 'approved_minor', 'status',
                  'public_response', 'decided_at', 'created_at', 'version']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    history = serializers.SerializerMethodField()
    cases = CaseSerializer(many=True, read_only=True)
    payment_state = serializers.SerializerMethodField()
    delivery_state = serializers.SerializerMethodField()
    sent_count = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'number', 'event', 'origin', 'order_state', 'payment_state', 'delivery_state', 'sent_count',
                  'customer_name', 'customer_phone', 'customer_email', 'customer_comment', 'subtotal_minor', 'discount_minor', 'promo_code', 'total_minor', 'currency',
                  'payment', 'event_snapshot', 'fan_id_answer', 'fan_id_help_state', 'delivery_due_at',
                  'items', 'history', 'cases', 'created_at', 'updated_at', 'version']

    def get_history(self, obj):
        public = [row for row in obj.history.all() if row.public_message]
        return OrderHistorySerializer(public, many=True).data

    def get_payment_state(self, obj):
        return money_summary(obj)['state']

    def get_delivery_state(self, obj):
        return sent_summary(obj)['state']

    def get_sent_count(self, obj):
        return sent_summary(obj)['sent_count']

    def get_payment(self, obj):
        summary = money_summary(obj)
        return {key: summary[key] for key in ['received_minor', 'refunded_minor', 'net_received_minor']}

    def get_currency(self, obj):
        return 'RUB'


class StaffOrderItemSerializer(OrderItemSerializer):
    class Meta(OrderItemSerializer.Meta):
        fields = OrderItemSerializer.Meta.fields + ['ticket_unit', 'purchase_price_minor']


class StaffHistorySerializer(OrderHistorySerializer):
    class Meta(OrderHistorySerializer.Meta):
        fields = OrderHistorySerializer.Meta.fields + ['internal_note', 'actor']


class StaffCaseSerializer(CaseSerializer):
    order_version = serializers.IntegerField(source='order.version', read_only=True)

    class Meta(CaseSerializer.Meta):
        fields = CaseSerializer.Meta.fields + ['user', 'internal_notes', 'decided_by', 'order_version']


class DeliverySerializer(serializers.ModelSerializer):
    items = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    order_version = serializers.IntegerField(source='order.version', read_only=True)

    class Meta:
        model = DeliveryRecord
        fields = ['id', 'order', 'order_version', 'items', 'recipient_email', 'sent_at', 'sent_by', 'note', 'message_id',
                  'status', 'void_reason', 'voided_at', 'created_at']


class StaffOrderSerializer(OrderSerializer):
    items = StaffOrderItemSerializer(many=True, read_only=True)
    history = StaffHistorySerializer(many=True, read_only=True)
    cases = StaffCaseSerializer(many=True, read_only=True)
    deliveries = DeliverySerializer(many=True, read_only=True)
    financial_entries = serializers.SerializerMethodField()

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ['user', 'manager', 'review_due_at', 'settlement_due_at', 'first_contact_at',
                  'confirmed_at', 'first_paid_at', 'internal_notes', 'ticket_request', 'quote', 'deliveries', 'financial_entries']

    def get_financial_entries(self, obj):
        from payments.serializers import FinancialEntrySerializer
        return FinancialEntrySerializer(obj.financial_entries.all(), many=True).data


class CancelOrderSerializer(VersionActionSerializer):
    reason = serializers.CharField(max_length=2000)
    no_pending_settlements = serializers.BooleanField(required=False, default=False)


class ContactSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    note = serializers.CharField(required=False, default='', allow_blank=True, max_length=2000)


class OrderOperationsSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    manager_id = serializers.UUIDField(required=False)
    internal_notes = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    review_due_at = serializers.DateTimeField(required=False)
    settlement_due_at = serializers.DateTimeField(required=False, allow_null=True)
    delivery_due_at = serializers.DateTimeField(required=False, allow_null=True)
    fan_id_help_state = serializers.ChoiceField(choices=['NOT_NEEDED', 'REQUESTED', 'IN_PROGRESS', 'INSTRUCTED'], required=False)


class CreateCaseSerializer(StrictSerializer):
    kind = serializers.ChoiceField(choices=['REFUND_REQUEST', 'CANCEL_REQUEST', 'DELIVERY_ISSUE', 'OTHER'], default='REFUND_REQUEST')
    item_ids = serializers.ListField(child=serializers.UUIDField(), required=False, min_length=1, max_length=100)
    reason = serializers.CharField(max_length=2000)
    requested_minor = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class RecordDeliverySerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    item_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=100)
    recipient_email = serializers.EmailField()
    sent_at = serializers.DateTimeField()
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    message_id = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def validate_item_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError('Позиции повторяются.')
        return value


class UpdateItemCostSerializer(VersionActionSerializer):
    reason = serializers.CharField(max_length=2000)
    purchase_price_minor = serializers.IntegerField(min_value=0)
    zero_confirmed = serializers.BooleanField(default=False)
