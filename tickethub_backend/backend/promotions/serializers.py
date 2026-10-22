from rest_framework import serializers
from core.serializers import StrictModelSerializer, StrictSerializer
from .models import PromoCode
from .services import save_promotion
from .calculations import normalize_code


class PromoPreviewSerializer(StrictSerializer):
    hold_id = serializers.UUIDField()
    code = serializers.CharField(min_length=3, max_length=40)


class PromoCodeSerializer(StrictModelSerializer):
    expected_version = serializers.IntegerField(min_value=1, write_only=True, required=False)
    usage_count = serializers.IntegerField(read_only=True)
    # Normalization happens before uniqueness validation, including for API writes.
    code = serializers.CharField(max_length=40)

    class Meta:
        model = PromoCode
        fields = ['id', 'code', 'description', 'kind', 'value', 'minimum_total_minor',
                  'maximum_discount_minor', 'starts_at', 'ends_at', 'is_active',
                  'usage_limit', 'per_user_limit', 'event', 'version', 'expected_version',
                  'usage_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'version', 'created_at', 'updated_at']

    def validate_code(self, value):
        try:
            return normalize_code(value)
        except ValueError:
            raise serializers.ValidationError('Код: 3–40 латинских букв, цифр, дефисов или подчёркиваний.')

    def create(self, validated_data):
        return save_promotion(None, validated_data)

    def update(self, instance, validated_data):
        return save_promotion(instance, validated_data)
