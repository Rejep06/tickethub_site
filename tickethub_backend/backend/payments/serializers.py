from rest_framework import serializers
from core.serializers import StrictSerializer
from .models import FinancialEntry


class FinancialEntrySerializer(serializers.ModelSerializer):
    order_version = serializers.IntegerField(source='order.version', read_only=True)

    class Meta:
        model = FinancialEntry
        fields = ['id', 'order', 'order_version', 'kind', 'amount_minor', 'occurred_at', 'method', 'reference',
                  'created_by', 'notes', 'direction', 'reversal_of', 'refund_case', 'created_at']


class MoneyOperationSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    amount_minor = serializers.IntegerField(min_value=1, max_value=10**12)
    occurred_at = serializers.DateTimeField()
    method = serializers.ChoiceField(choices=['BANK_CARD', 'SBP', 'BANK_TRANSFER', 'CASH', 'OTHER'])
    reference = serializers.CharField(max_length=200)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class RecordPaymentSerializer(MoneyOperationSerializer):
    kind = serializers.ChoiceField(choices=['PAYMENT', 'DIRECT_EXPENSE', 'SUPPLIER_REFUND'])


class ReverseEntrySerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    occurred_at = serializers.DateTimeField()
    reason = serializers.CharField(max_length=2000)


class CaseDecisionSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    decision = serializers.ChoiceField(choices=['APPROVED', 'REJECTED', 'IN_PROGRESS', 'NEED_INFO', 'CLOSED'])
    public_response = serializers.CharField(max_length=2000)
    amount_minor = serializers.IntegerField(min_value=1, required=False)
    internal_notes = serializers.CharField(required=False, default='', allow_blank=True, max_length=2000)


class ApproveRefundSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    amount_minor = serializers.IntegerField(min_value=1)
    public_response = serializers.CharField(max_length=2000)
    internal_notes = serializers.CharField(required=False, default='', allow_blank=True, max_length=2000)


class RejectRefundSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    public_response = serializers.CharField(max_length=2000)
    internal_notes = serializers.CharField(required=False, default='', allow_blank=True, max_length=2000)
