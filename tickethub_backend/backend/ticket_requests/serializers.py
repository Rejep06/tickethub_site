from django.utils import timezone
from rest_framework import serializers
from core.serializers import StrictSerializer
from events.serializers import EventSerializer
from .models import TicketRequest, Quote, QuoteItem


class CreateRequestSerializer(StrictSerializer):
    event_id = serializers.UUIDField(required=False, allow_null=True)
    custom_event_name = serializers.CharField(max_length=250, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    desired_date = serializers.DateField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1, max_value=100)
    preferences = serializers.CharField(max_length=500, required=False, allow_blank=True)
    together_required = serializers.BooleanField(required=False, default=False)
    budget_minor = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    accepted_documents = serializers.DictField(child=serializers.IntegerField(min_value=1), required=False, default=dict)


class QuoteItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuoteItem
        fields = ['id', 'name_ru', 'name_en', 'sector', 'row', 'seat_number', 'price_minor']


class QuoteEventSerializer(EventSerializer):
    def get_orderable(self, obj):
        from events.services import check_orderable
        from core.errors import BusinessError
        try:
            check_orderable(obj, timezone.now(), from_quote=True)
            return True
        except BusinessError:
            return False


class QuoteSerializer(serializers.ModelSerializer):
    items = QuoteItemSerializer(many=True, read_only=True)
    event = QuoteEventSerializer(read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Quote
        fields = ['id', 'ticket_request', 'event', 'version', 'status', 'expires_at', 'total_minor', 'public_comment', 'items', 'sent_at', 'together_confirmed']

    def get_status(self, obj):
        return 'EXPIRED' if obj.status in ['DRAFT', 'SENT'] and obj.expires_at <= timezone.now() else obj.status


class RequestSerializer(serializers.ModelSerializer):
    quotes = serializers.SerializerMethodField()

    class Meta:
        model = TicketRequest
        fields = ['id', 'number', 'event', 'custom_event_name', 'city', 'desired_date', 'quantity', 'preferences',
                  'together_required', 'budget_minor', 'comment', 'status', 'customer_name', 'customer_email',
                  'customer_phone', 'public_response', 'quotes', 'created_at', 'updated_at', 'version']

    def get_quotes(self, obj):
        return QuoteSerializer([q for q in obj.quotes.all() if q.status != 'DRAFT'], many=True, context=self.context).data


class StaffQuoteItemSerializer(QuoteItemSerializer):
    class Meta(QuoteItemSerializer.Meta):
        fields = QuoteItemSerializer.Meta.fields + ['ticket_unit']


class StaffQuoteSerializer(QuoteSerializer):
    items = StaffQuoteItemSerializer(many=True, read_only=True)
    request_version = serializers.IntegerField(source='ticket_request.version', read_only=True)

    class Meta(QuoteSerializer.Meta):
        fields = QuoteSerializer.Meta.fields + ['request_version']


class StaffRequestSerializer(RequestSerializer):
    class Meta(RequestSerializer.Meta):
        fields = RequestSerializer.Meta.fields + ['user', 'manager', 'internal_notes']

    def get_quotes(self, obj):
        return StaffQuoteSerializer(obj.quotes.all(), many=True, context=self.context).data


class RequestActionSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    manager_id = serializers.UUIDField(required=False)
    event_id = serializers.UUIDField(required=False)
    internal_notes = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    public_response = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=['IN_PROGRESS', 'CANCELLED', 'REJECTED'], required=False)


class QuoteItemInputSerializer(StrictSerializer):
    ticket_unit_id = serializers.UUIDField()
    price_minor = serializers.IntegerField(min_value=1, max_value=10**12)


class CreateQuoteSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    event_id = serializers.UUIDField()
    expires_at = serializers.DateTimeField()
    public_comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    items = QuoteItemInputSerializer(many=True, allow_empty=False)
    together_confirmed = serializers.BooleanField(required=False, default=False)

    def validate_items(self, value):
        if len(value) > 100:
            raise serializers.ValidationError('Максимум 100 билетов.')
        return value


class QuoteCheckoutSerializer(StrictSerializer):
    expected_total_minor = serializers.IntegerField(min_value=1)
