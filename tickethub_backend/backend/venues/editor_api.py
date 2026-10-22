from rest_framework import serializers
from rest_framework.response import Response
from core.api import payload
from core.errors import BusinessError
from core.serializers import StrictSerializer
from .geometry import GeometryError, generate_block, parse_csv, MAX_BATCH
from .editor_services import edit_seats


class EditSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    create = serializers.ListField(child=serializers.DictField(), max_length=MAX_BATCH, default=list)
    update = serializers.ListField(child=serializers.DictField(), max_length=MAX_BATCH, default=list)
    delete = serializers.ListField(child=serializers.UUIDField(), max_length=MAX_BATCH, default=list)


class BlockSerializer(StrictSerializer):
    sector = serializers.CharField(max_length=50)
    rows = serializers.IntegerField(min_value=1, max_value=100, default=5)
    seats_per_row = serializers.IntegerField(min_value=1, max_value=500, default=12)
    row_start = serializers.IntegerField(min_value=1, default=1)
    seat_start = serializers.IntegerField(min_value=1, default=1)
    seat_step = serializers.ChoiceField(choices=[-2, -1, 1, 2], default=1)
    x = serializers.FloatField(default=0.15)
    y = serializers.FloatField(default=0.15)
    width = serializers.FloatField(default=0.5)
    row_spacing = serializers.FloatField(default=0.04)
    angle = serializers.FloatField(default=0)
    curve = serializers.FloatField(default=0)
    reverse_alternate = serializers.BooleanField(default=False)
    aisles_after = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=499, default=list)


class CSVSerializer(StrictSerializer):
    text = serializers.CharField(max_length=512 * 1024, trim_whitespace=False)


def preview_block(request):
    try:
        result = generate_block(**payload(BlockSerializer, request))
    except (GeometryError, OverflowError, ValueError) as exc:
        raise BusinessError('INVALID_GEOMETRY', str(exc), status=400) from exc
    return Response({'seats': result, 'count': len(result), 'saved': False})


def preview_csv(request):
    try:
        result = parse_csv(payload(CSVSerializer, request)['text'])
    except GeometryError as exc:
        raise BusinessError('INVALID_CSV', str(exc), status=400) from exc
    return Response({'seats': result, 'count': len(result), 'saved': False})


def bulk_edit(request, plan_id):
    return Response(edit_seats(plan_id, **payload(EditSerializer, request)))
