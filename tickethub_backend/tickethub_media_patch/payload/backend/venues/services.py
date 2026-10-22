from decimal import Decimal
from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from core.errors import require, check_version
from .models import SeatingPlan, Seat, Venue
from .geometry import MAX_SEATS


@transaction.atomic
def save_plan(instance, data):
    expected = data.pop('expected_version', None)
    if instance:
        plan = get_object_or_404(SeatingPlan.objects.select_for_update(), pk=instance.pk)
        check_version(plan, expected)
        require(plan.status == 'DRAFT', 'PLAN_IMMUTABLE', 'Опубликованная схема неизменяема.')
    else:
        plan = SeatingPlan()
    for key, value in data.items():
        setattr(plan, key, value)
    plan.full_clean()
    if instance:
        plan.version += 1
    plan.save()
    return plan


@transaction.atomic
def publish_plan(plan_id, expected_version):
    plan = get_object_or_404(SeatingPlan.objects.select_for_update(), pk=plan_id)
    check_version(plan, expected_version)
    require(plan.status == 'DRAFT' and plan.seats.exists(), 'INVALID_PLAN', 'Нужен черновик с местами.')
    if plan.image:
        require(plan.rights_confirmed and plan.rights_source,
                'INVALID_PLAN', 'Подтвердите права на загруженный фон.')
    # Coordinates are useful without a background: render a neutral canvas.
    plan.full_clean()
    plan.status = 'PUBLISHED'
    plan.version += 1
    plan.save()
    return plan


@transaction.atomic
def clone_plan(plan_id):
    original = get_object_or_404(SeatingPlan.objects.select_for_update(), pk=plan_id)
    copy = SeatingPlan.objects.create(
        venue=original.venue, name=original.name + ' (копия)',
        image=original.image.name, rights_source=original.rights_source,
        rights_confirmed=original.rights_confirmed,
        # A manual clone keeps the useful picture/point cloud but is detached from provider sync.
        external_background_url=original.external_background_url, external_width=original.external_width,
        external_height=original.external_height, external_geometry=original.external_geometry,
        external_sectors=original.external_sectors,
    )
    Seat.objects.bulk_create([Seat(plan=copy, sector=s.sector, row=s.row, number=s.number, x=s.x, y=s.y,
                                  adjacency_group=s.adjacency_group, adjacency_position=s.adjacency_position,
                                  external_point_key=s.external_point_key if not s.labels_known else '')
                              for s in original.seats.all()])
    return copy


@transaction.atomic
def save_seat(instance, data):
    plan_id = instance.plan_id if instance else data['plan'].id
    plan = get_object_or_404(SeatingPlan.objects.select_for_update(), pk=plan_id)
    require(plan.status == 'DRAFT', 'PLAN_IMMUTABLE', 'Изменять можно только черновик.')
    require(instance is not None or plan.seats.count() < MAX_SEATS, 'PLAN_LIMIT', f'Максимум {MAX_SEATS} мест.')
    seat = get_object_or_404(Seat, pk=instance.pk) if instance else Seat()
    require(not seat.external_point_key, 'EXTERNAL_GEOMETRY_READONLY',
            'Импортированные координаты изменяет синхронизация. Создайте ручную копию или новое место.')
    require(all(data.get(f, getattr(seat, f)) for f in ['sector', 'row', 'number']),
            'SEAT_LABELS_REQUIRED', 'Нужны сектор, ряд и номер.')
    for key, value in data.items():
        setattr(seat, key, value)
    seat.full_clean()
    seat.save()
    plan.version += 1
    plan.save(update_fields=['version', 'updated_at'])
    return seat


@transaction.atomic
def delete_seat(seat_id):
    seat = get_object_or_404(Seat, pk=seat_id)
    plan = get_object_or_404(SeatingPlan.objects.select_for_update(), pk=seat.plan_id)
    require(not seat.external_point_key, 'EXTERNAL_GEOMETRY_READONLY', 'Импортированную точку нельзя удалить вручную.')
    require(plan.status == 'DRAFT' and not seat.units.exists(), 'PLAN_IMMUTABLE', 'Место нельзя удалить.')
    seat.delete()
    plan.version += 1
    plan.save(update_fields=['version', 'updated_at'])


@transaction.atomic
def create_row(plan_id, sector, row, numbers, x1, y1, x2, y2, adjacency_group=''):
    plan = get_object_or_404(SeatingPlan.objects.select_for_update(), pk=plan_id)
    require(plan.status == 'DRAFT', 'PLAN_IMMUTABLE', 'Нужен черновик схемы.')
    require(plan.seats.count() + len(numbers) <= MAX_SEATS, 'PLAN_LIMIT', f'Максимум {MAX_SEATS} мест.')
    require(len(set(numbers)) == len(numbers), 'DUPLICATE_SEAT', 'Номера повторяются.')
    seats = []
    denominator = Decimal(max(len(numbers) - 1, 1))
    for i, number in enumerate(numbers):
        fraction = Decimal(i) / denominator
        seat = Seat(plan=plan, sector=sector, row=row, number=number,
                    x=(x1 + (x2 - x1) * fraction).quantize(Decimal('0.000001')),
                    y=(y1 + (y2 - y1) * fraction).quantize(Decimal('0.000001')),
                    adjacency_group=adjacency_group, adjacency_position=i if adjacency_group else None)
        seat.full_clean()
        seats.append(seat)
    Seat.objects.bulk_create(seats)
    plan.version += 1
    plan.save(update_fields=['version', 'updated_at'])
    return seats
