from rest_framework import serializers
from core.serializers import StrictSerializer
from .services import CLIENT_STEPS


class ClientEventSerializer(StrictSerializer):
    event_id = serializers.UUIDField()
    client_event_id = serializers.UUIDField()
    event_type = serializers.ChoiceField(choices=CLIENT_STEPS)
    analytics_consent = serializers.BooleanField()

    def validate_analytics_consent(self, value):
        if not value:
            raise serializers.ValidationError('Без согласия веб-аналитика не сохраняется.')
        return value


class ReportFilterSerializer(serializers.Serializer):
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    event = serializers.UUIDField(required=False)
    category = serializers.UUIDField(required=False)

    def validate(self, attrs):
        if attrs.get('date_from') and attrs.get('date_to') and attrs['date_from'] >= attrs['date_to']:
            raise serializers.ValidationError('Начало периода должно быть раньше конца.')
        return attrs
