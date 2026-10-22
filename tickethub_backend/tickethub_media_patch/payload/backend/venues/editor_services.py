"""Batch edits use the same plan lock as the existing single-seat operations."""
import uuid
from django.db import transaction
from django.shortcuts import get_object_or_404
from core.errors import require, check_version, BusinessError
from .models import SeatingPlan, Seat
from .geometry import MAX_SEATS, MAX_BATCH, GeometryError, normalize_seat

SEAT_FIELDS = ['sector', 'row', 'number', 'x', 'y', 'adjacency_group', 'adjacency_position']


def normalized(data):
    try:
        return normalize_seat(data)
    except GeometryError as exc:
        raise BusinessError('INVALID_GEOMETRY', str(exc), status=400) from exc


def as_uuid(value):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise BusinessError('INVALID_SEAT_ID', 'Некорректный ID места.', status=400) from None


@transaction.atomic
def edit_seats(plan_id, *, expected_version, create=(), update=(), delete=()):
    plan = get_object_or_404(SeatingPlan.objects.select_for_update(), pk=plan_id)
    check_version(plan, expected_version)
    require(plan.status == 'DRAFT', 'PLAN_IMMUTABLE', 'Опубликованная схема неизменяема. Создайте копию.')
    require(0 < len(create) + len(update) + len(delete) <= MAX_BATCH,
            'BATCH_LIMIT', f'Нужно от 1 до {MAX_BATCH} изменений.', status=400)
    old = {s.id: s for s in plan.seats.all()}
    update_ids = [as_uuid(data.get('id')) for data in update]
    delete_ids = [as_uuid(value) for value in delete]
    all_ids = update_ids + delete_ids
    require(len(set(all_ids)) == len(all_ids), 'DUPLICATE_SEAT', 'ID повторяется в операции.', status=400)
    require(set(all_ids) <= old.keys(), 'SEAT_NOT_FOUND', 'Место не принадлежит этой схеме.', status=404)
    require(not any(old[key].external_point_key for key in all_ids),
            'EXTERNAL_GEOMETRY_READONLY', 'Импортированные координаты защищены; редактируйте ручную копию.')
    require(not Seat.objects.filter(pk__in=delete_ids, units__isnull=False).exists(),
            'SEAT_IN_USE', 'Нельзя удалить место с существующими билетами.')
    # Once stock refers to a plan, even a mistakenly DRAFT plan must not change identity.
    require(not Seat.objects.filter(plan=plan, units__isnull=False).exists(),
            'PLAN_IN_USE', 'Схема уже используется билетами. Сначала создайте новую версию.')
    changes = []
    for data, seat_id in zip(update, update_ids):
        require(set(data) <= set(SEAT_FIELDS) | {'id'}, 'UNKNOWN_FIELD', 'Неизвестное поле места.', status=400)
        seat = old[seat_id]
        merged = {f: getattr(seat, f) for f in SEAT_FIELDS}
        merged.update({k: v for k, v in data.items() if k != 'id'})
        changes.append((seat, normalized(merged)))
    # Changing part of a row can invalidate a previous 'seats together' claim.
    # Clear affected adjacency groups rather than silently preserving that claim.
    geometry_fields = ['sector', 'row', 'number', 'x', 'y']
    affected_groups = {old[key].adjacency_group for key in delete_ids if old[key].adjacency_group}
    affected_groups.update(seat.adjacency_group for seat, data in changes
                           if seat.adjacency_group and any(getattr(seat, k) != data[k] for k in geometry_fields))
    by_id = {seat.id: (seat, data) for seat, data in changes}
    for seat in old.values():
        if seat.id not in delete_ids and seat.adjacency_group in affected_groups:
            data = by_id[seat.id][1] if seat.id in by_id else {f: getattr(seat, f) for f in SEAT_FIELDS}
            data.update(adjacency_group='', adjacency_position=None)
            by_id[seat.id] = (seat, data)
    changes = list(by_id.values())
    update_ids = list(by_id)
    created = [Seat(plan=plan, **normalized(data)) for data in create]
    require(len(old) - len(delete_ids) + len(created) <= MAX_SEATS,
            'PLAN_LIMIT', f'Максимум {MAX_SEATS} мест в схеме.')
    desired = {key: (value.sector, value.row, value.number) for key, value in old.items()
               if key not in set(delete_ids) | set(update_ids) and value.labels_known}
    positions = list(desired.values())
    positions.extend((data['sector'], data['row'], data['number']) for _, data in changes)
    positions.extend((s.sector, s.row, s.number) for s in created)
    require(len(positions) == len(set(positions)), 'DUPLICATE_SEAT', 'Сектор, ряд и номер должны быть уникальны.')
    Seat.objects.filter(pk__in=delete_ids).delete()
    # Temporary unique numbers allow swapping/renumbering in one atomic edit.
    # They are never observable outside this transaction.
    occupied = set(positions) | {(s.sector, s.row, s.number) for s in old.values()}
    for seat, _ in changes:
        while True:
            temporary = '~' + uuid.uuid4().hex[:28]
            if (seat.sector, seat.row, temporary) not in occupied:
                break
        occupied.add((seat.sector, seat.row, temporary))
        seat.number = temporary
    if changes:
        Seat.objects.bulk_update([seat for seat, _ in changes], ['number'], batch_size=500)
        for seat, data in changes:
            for field, value in data.items():
                setattr(seat, field, value)
        Seat.objects.bulk_update([seat for seat, _ in changes], SEAT_FIELDS, batch_size=500)
    Seat.objects.bulk_create(created, batch_size=500)
    plan.version += 1
    plan.save(update_fields=['version', 'updated_at'])
    return {'version': plan.version, 'created_ids': [str(s.id) for s in created],
            'created': len(created), 'updated': len(changes), 'deleted': len(delete_ids)}
