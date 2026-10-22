from rest_framework import serializers
from core.serializers import StrictSerializer
from .models import ExternalEvent, ExternalDate


class ImportSerializer(StrictSerializer):
    provider = serializers.ChoiceField(choices=['portalbilet'], default='portalbilet')
    url = serializers.CharField(max_length=600)
    mode = serializers.ChoiceField(choices=['IMPORT_ONLY'], default='IMPORT_ONLY')
    preview = serializers.BooleanField(default=False)


class DateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalDate
        fields = ['id', 'external_date_id', 'event', 'source_active', 'source_start_at', 'last_seen_at']


class SourceSerializer(serializers.ModelSerializer):
    dates = DateSerializer(many=True, read_only=True)

    class Meta:
        model = ExternalEvent
        fields = ['id', 'provider', 'external_event_id', 'event_source_id', 'external_place_id',
                  'external_layout_id', 'url', 'title', 'venue', 'status', 'last_attempt_at',
                  'last_metadata_sync_at', 'diagnostics', 'dates']
