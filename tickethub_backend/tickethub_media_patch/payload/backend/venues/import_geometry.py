"""Materialize every coordinate, independently of current ticket availability."""
from decimal import Decimal, InvalidOperation
import hashlib
from core.errors import require
from .models import Seat


def point_key(x, y):
    # Coordinates have already been normalized to 6 decimals by the verified parser.
    try:
        x, y = (Decimal(str(value)).quantize(Decimal('0.000001')) for value in (x, y))
    except (InvalidOperation, ValueError):
        raise ValueError('Некорректная координата.') from None
    if not x.is_finite() or not y.is_finite() or not (0 <= x <= 1 and 0 <= y <= 1):
        raise ValueError('Координата вне схемы.')
    x, y = (abs(value) if value == 0 else value for value in (x, y))
    return hashlib.sha256(f'{x:.6f}:{y:.6f}'.encode('ascii')).hexdigest()


def materialize_geometry(plan):
    """Caller MUST hold the plan row lock. Adds geometry; never invents labels or stock."""
    if not plan.external_geometry:
        return 0
    require(len(plan.external_geometry) <= 50000, 'PLAN_LIMIT', 'Максимум 50 000 точек.')
    existing = list(plan.seats.all())
    by_key = {s.external_point_key: s for s in existing if s.external_point_key}
    unmapped = {}
    for seat in existing:
        if not seat.external_point_key:
            key = point_key(seat.x, seat.y)
            unmapped.setdefault(key, []).append(seat)
    created, linked, seen = [], [], set()
    for x, y in plan.external_geometry:
        key = point_key(x, y)
        require(key not in seen, 'GEOMETRY_COLLISION', 'Две точки имеют одинаковые нормализованные координаты.')
        seen.add(key)
        if key in by_key:
            continue
        candidates = unmapped.get(key, [])
        require(len(candidates) <= 1, 'GEOMETRY_COLLISION', 'У координаты несколько локальных мест. Проверьте схему.')
        if candidates:
            seat = candidates[0]
            seat.external_point_key = key
            linked.append(seat)
        else:
            # Blank labels explicitly mean "not provided", never fictional row/seat numbers.
            seat = Seat(plan=plan, sector='', row='', number='', x=x, y=y, external_point_key=key)
            created.append(seat)
        by_key[key] = seat
    require(len(existing) + len(created) <= 50000, 'PLAN_LIMIT', 'Максимум 50 000 мест.')
    if linked:
        Seat.objects.bulk_update(linked, ['external_point_key'], batch_size=500)
    if created:
        Seat.objects.bulk_create(created, batch_size=500)
    if linked or created:
        plan.version += 1
        plan.save(update_fields=['version', 'updated_at'])
    return len(created)
