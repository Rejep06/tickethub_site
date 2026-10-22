"""Pure calculations for the layout editor; coordinates always remain in [0, 1]."""
import csv
import io
import math
from decimal import Decimal, InvalidOperation

MAX_SEATS = 50000
MAX_BATCH = 2000
PRECISION = Decimal('0.000001')


class GeometryError(ValueError):
    pass


def coordinate(value):
    try:
        result = Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation):
        raise GeometryError('Координата должна быть числом.') from None
    if not result.is_finite() or not 0 <= result <= 1:
        raise GeometryError('Координаты должны находиться в диапазоне от 0 до 1.')
    return result.quantize(PRECISION)


def label(value, limit, name):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise GeometryError(f'{name}: укажите непустой текст длиной до {limit} символов.')
    return value.strip()


def normalize_seat(data):
    allowed = {'sector', 'row', 'number', 'x', 'y', 'adjacency_group', 'adjacency_position'}
    if set(data) - allowed:
        raise GeometryError('Обнаружены неизвестные поля места.')
    group = data.get('adjacency_group', '')
    position = data.get('adjacency_position')
    if not isinstance(group, str) or len(group) > 80:
        raise GeometryError('Слишком длинная группа соседства.')
    if position is not None and (type(position) is not int or not 0 <= position <= 1000000):
        raise GeometryError('Недопустимая позиция соседства.')
    return {
        'sector': label(data.get('sector'), 50, 'Сектор'),
        'row': label(data.get('row'), 30, 'Ряд'),
        'number': label(data.get('number'), 30, 'Номер'),
        'x': coordinate(data.get('x')), 'y': coordinate(data.get('y')),
        'adjacency_group': group, 'adjacency_position': position,
    }


def generate_block(*, sector, rows=5, seats_per_row=12, row_start=1, seat_start=1,
                   seat_step=1, x=0.15, y=0.15, width=0.5, row_spacing=0.04,
                   angle=0, curve=0, reverse_alternate=False, aisles_after=None):
    """Parallel straight/curved rows. Aisles split adjacency; they do not invent seats."""
    if type(rows) is not int or type(seats_per_row) is not int:
        raise GeometryError('Количество рядов и мест должно быть целым.')
    if not 1 <= rows <= 100 or not 1 <= seats_per_row <= 500 or rows * seats_per_row > MAX_BATCH:
        raise GeometryError(f'За одну операцию можно добавить до {MAX_BATCH} мест.')
    if any(type(v) is not int for v in (row_start, seat_start, seat_step)):
        raise GeometryError('Начальные номера и шаг должны быть целыми.')
    if seat_step not in (-2, -1, 1, 2) or row_start < 1 or seat_start < 1:
        raise GeometryError('Номера начинаются с 1; шаг нумерации: 1, 2, -1 или -2.')
    if seat_start + seat_step * (seats_per_row - 1) < 1:
        raise GeometryError('Нумерация не должна уходить ниже 1.')
    values = [float(v) for v in (x, y, width, row_spacing, angle, curve)]
    if not all(math.isfinite(v) for v in values):
        raise GeometryError('Параметры геометрии должны быть конечными числами.')
    x, y, width, row_spacing, angle, curve = values
    if width < 0 or row_spacing <= 0 or (seats_per_row > 1 and width <= 0):
        raise GeometryError('Ширина ряда и расстояние между рядами должны быть положительными.')
    aisles = aisles_after or []
    if len(set(aisles)) != len(aisles) or any(type(v) is not int or not 1 <= v < seats_per_row for v in aisles):
        raise GeometryError('Проход задаётся позицией между соседними местами ряда.')
    angle = math.radians(angle)
    ca, sa = math.cos(angle), math.sin(angle)
    result = []
    for r in range(rows):
        group, group_position = 0, 0
        for s in range(seats_per_row):
            if s in aisles:
                group += 1
                group_position = 0
            t = s / max(seats_per_row - 1, 1)
            dx, dy = width * t, r * row_spacing + 4 * curve * t * (1 - t)
            number_index = seats_per_row - s - 1 if reverse_alternate and r % 2 else s
            row = str(row_start + r)
            result.append(normalize_seat({
                'sector': sector, 'row': row, 'number': str(seat_start + seat_step * number_index),
                'x': x + ca * dx - sa * dy, 'y': y + sa * dx + ca * dy,
                'adjacency_group': f'{sector}:{row}:{group}', 'adjacency_position': group_position,
            }))
            group_position += 1
    return result


def parse_csv(text):
    """CSV is a supported LOCAL input format, not an assumed PortalBilet payload."""
    if not isinstance(text, str) or len(text.encode('utf-8')) > 512 * 1024:
        raise GeometryError('CSV должен быть меньше 512 КБ.')
    text = text.lstrip('\ufeff')
    first = text.splitlines()[0] if text.splitlines() else ''
    delimiter = ';' if ';' in first else ','
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if set(reader.fieldnames or []) != {'sector', 'row', 'number', 'x', 'y'}:
        raise GeometryError('Нужны колонки sector,row,number,x,y. Координаты — от 0 до 1.')
    result, used = [], set()
    for line, record in enumerate(reader, start=2):
        try:
            record['x'] = record['x'].replace(',', '.')
            record['y'] = record['y'].replace(',', '.')
            seat = normalize_seat(record)
        except (GeometryError, AttributeError, KeyError) as exc:
            raise GeometryError(f'Строка {line}: {exc}') from None
        key = (seat['sector'], seat['row'], seat['number'])
        if key in used:
            raise GeometryError(f'Строка {line}: повторяется сектор/ряд/место.')
        used.add(key)
        result.append(seat)
        if len(result) > MAX_BATCH:
            raise GeometryError(f'За одну загрузку можно добавить до {MAX_BATCH} мест.')
    if not result:
        raise GeometryError('CSV не содержит мест.')
    return result
