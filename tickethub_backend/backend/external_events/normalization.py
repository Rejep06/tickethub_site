"""Normalize the PortalBilet payloads that were verified from a real capture.

Important distinction:
- hall coordinates describe static geometry;
- assigned-seat tickets describe availability for one event date;
- standing tickets are separate inventory and never become fake seats.
"""
import hashlib
import json
import math
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html.parser import HTMLParser
from urllib.parse import urlsplit
from .http import ProviderError
from .provider import external_id


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output, self.ignored = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'iframe', 'object'}:
            self.ignored += 1
        if not self.ignored and tag in {'p', 'br', 'div', 'li', 'h1', 'h2', 'h3'}:
            self.output.append('\n')

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'iframe', 'object'} and self.ignored:
            self.ignored -= 1
        if not self.ignored and tag in {'p', 'div', 'li'}:
            self.output.append('\n')

    def handle_data(self, data):
        if not self.ignored:
            self.output.append(data)


def text(value, max_length=20000):
    if not isinstance(value, str):
        return ''
    parser = TextOnly()
    parser.feed(value[:max_length * 3])
    return '\n'.join(line.strip() for line in ''.join(parser.output).splitlines() if line.strip())[:max_length]


def short_text(value, maximum, *, field):
    value = str(value).strip() if value is not None else ''
    if not value or len(value) > maximum:
        raise ProviderError('PROVIDER_SCHEMA', f'Некорректное поле {field} в ответе источника.')
    return value


def walk_objects(value, *, limit=100000):
    queue = [value]
    seen = 0
    while queue:
        item = queue.pop()
        seen += 1
        if seen > limit:
            raise ProviderError('PROVIDER_COMPLEXITY', 'JSON слишком сложен для безопасного разбора.')
        if isinstance(item, dict):
            yield item
            queue.extend(item.values())
        elif isinstance(item, list):
            queue.extend(item)


def bootstrap(payload):
    candidates = []
    for node in walk_objects(payload):
        if 'event_source_id' in node and isinstance(node.get('place'), dict) and 'id' in node:
            candidates.append(node)
    unique = {json.dumps(node, sort_keys=True, ensure_ascii=False): node for node in candidates}
    if len(unique) != 1:
        raise ProviderError('PAGE_DATA_SCHEMA', 'Нельзя однозначно найти event в page-data. Сохранённый ответ нужно проверить.')
    event = next(iter(unique.values()))
    place = event['place']
    location = place.get('location') if isinstance(place.get('location'), dict) else {}
    country = location.get('country') if isinstance(location.get('country'), dict) else {}
    result = {
        'external_event_id': external_id(event['id']),
        'event_source_id': external_id(event['event_source_id']),
        'external_place_id': external_id(place.get('id')),
        'external_layout_id': external_id(event['hall_layout_id']) if event.get('hall_layout_id') else '',
        'title': text(event.get('title') or event.get('affiche_title'), 250),
        'description': text(event.get('description') or event.get('annotation')),
        'place_name': text(place.get('name') or place.get('title'), 200),
        'address': text(place.get('address'), 300),
        'city': text(location.get('name'), 100),
        'country_name': text(country.get('name') or country.get('title'), 100),
        'dates': event.get('dates'),
        'source_metadata': {key: event.get(key) for key in
                            ['event_category', 'category', 'breadcrumbs', 'persons', 'participants',
                             'preview', 'cover', 'hall', 'annotation']},
        'place_metadata': place,
    }
    if not result['title'] or not result['place_name']:
        raise ProviderError('PAGE_DATA_SCHEMA', 'Не найдены названия события/площадки. Нужна проверка структуры ответа.')
    # selectedEventId is intentionally never inspected: in the captured page it is a date/session ID.
    return result


def dates_list(payload):
    if isinstance(payload, dict):
        candidates = [payload[key] for key in ('dates', 'data') if isinstance(payload.get(key), list)]
        if len(candidates) != 1:
            raise ProviderError('DATES_SCHEMA', 'Неизвестная структура списка дат.')
        payload = candidates[0]
    if not isinstance(payload, list) or any(not isinstance(row, dict) or 'id' not in row for row in payload):
        raise ProviderError('DATES_SCHEMA', 'Источник не вернул список дат с идентификаторами.')
    identifiers = [external_id(row['id']) for row in payload]
    if len(set(identifiers)) != len(identifiers):
        raise ProviderError('DATES_SCHEMA', 'В ответе повторяется идентификатор даты.')
    return payload


def parse_date(row):
    """Only accept an offset-aware timestamp; a naive provider time stays a reviewable draft."""
    results = []
    for name in ('start_at', 'starts_at', 'startsAt', 'started_at', 'datetime', 'date'):
        value = row.get(name)
        if not isinstance(value, str) or 'T' not in value:
            continue
        try:
            result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            continue
        if result.utcoffset() is not None:
            results.append(result)
    return results[0] if results and all(value == results[0] for value in results) else None


def safe_asset_url(value):
    if not value:
        return ''
    try:
        parts = urlsplit(str(value))
    except ValueError:
        raise ProviderError('LAYOUT_SCHEMA', 'Некорректный URL фона схемы.') from None
    if parts.scheme != 'https' or parts.hostname not in {'cdn.pbilet.com', 'cdn.pbilet.net', 'picture.portalbilet.ru'}:
        raise ProviderError('LAYOUT_SCHEMA', 'Источник вернул неподдерживаемый домен фона схемы.')
    return str(value)


def _number(value, *, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ProviderError('PROVIDER_SCHEMA', f'Поле {field} должно быть числом.')
    return float(value)


def normalize_layout(payload, *, expected_layout_id=None):
    """Verified 2026-10-07 payload: id, coordinates[{x,y}], width, height, bg."""
    if not isinstance(payload, dict):
        raise ProviderError('LAYOUT_SCHEMA', 'Неизвестная структура coordinates.')
    layout_id = external_id(payload.get('id'))
    if expected_layout_id and layout_id != external_id(expected_layout_id):
        raise ProviderError('LAYOUT_SCHEMA', 'ID полученной схемы не совпадает с мероприятием.')
    width = payload.get('width')
    height = payload.get('height')
    if isinstance(width, bool) or isinstance(height, bool) or not isinstance(width, int) or not isinstance(height, int):
        raise ProviderError('LAYOUT_SCHEMA', 'Размеры схемы должны быть целыми числами.')
    if not (1 <= width <= 50000 and 1 <= height <= 50000):
        raise ProviderError('LAYOUT_SCHEMA', 'Некорректные размеры схемы.')
    rows = payload.get('coordinates')
    if not isinstance(rows, list) or not rows or len(rows) > 50000:
        raise ProviderError('LAYOUT_SCHEMA', 'Некорректный список координат схемы.')
    points, point_set = [], set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {'x', 'y'}:
            raise ProviderError('LAYOUT_SCHEMA', f'Неизвестная точка coordinates[{index}].')
        x = _number(row['x'], field='coordinates.x')
        y = _number(row['y'], field='coordinates.y')
        if x < 0 or y < 0 or x > width or y > height:
            raise ProviderError('LAYOUT_SCHEMA', 'Координата выходит за размеры схемы.')
        pixel = (x, y)
        if pixel in point_set:
            raise ProviderError('LAYOUT_SCHEMA', 'В coordinates есть повторяющаяся точка.')
        point_set.add(pixel)
        points.append([round(x / width, 6), round(y / height, 6)])
    return {
        'external_layout_id': layout_id,
        'width': width,
        'height': height,
        'background_url': safe_asset_url(payload.get('bg')),
        'points': points,
        'pixel_points': point_set,
    }


def money_minor(value, *, field='price'):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ProviderError('TICKET_SCHEMA', f'Некорректное денежное поле {field}.') from None
    if not amount.is_finite() or amount < 0:
        raise ProviderError('TICKET_SCHEMA', f'Некорректное денежное поле {field}.')
    return int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def normalize_assigned_tickets(payload, *, event_date_id, layout):
    """Decode the real compact ticket structure and verify every seat against coordinates.

    Observed stable local seat identity is (layout, sector, row, number). The ticket's
    x/y pair is the verified geometry join: every captured ticket point existed exactly
    once in coordinates.json. ticket.d is retained as provider ticket/listing ID, not
    treated as the physical seat ID.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get('sectors'), list):
        raise ProviderError('TICKET_SCHEMA', 'Неизвестная структура tickets.')
    expected_date = external_id(event_date_id)
    point_set = layout['pixel_points']
    result, sectors, labels, used_points = [], [], set(), set()
    for sector_index, sector in enumerate(payload['sectors']):
        if not isinstance(sector, dict):
            raise ProviderError('TICKET_SCHEMA', 'Некорректный сектор tickets.')
        sector_name = short_text(sector.get('i'), 50, field='sector.i')
        capacity = sector.get('all')
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 0:
            raise ProviderError('TICKET_SCHEMA', 'Некорректная вместимость сектора.')
        sector_id = str(sector.get('d') or '')[:100]
        path = str(sector.get('o') or '')
        if len(path) > 100000:
            raise ProviderError('TICKET_SCHEMA', 'SVG path сектора слишком большой.')
        sectors.append({'name': sector_name, 'external_id': sector_id, 'capacity': capacity, 'path': path})
        rows = sector.get('r')
        if not isinstance(rows, list):
            raise ProviderError('TICKET_SCHEMA', 'Некорректный список рядов.')
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('s'), list):
                raise ProviderError('TICKET_SCHEMA', 'Некорректная структура ряда.')
            row_name = short_text(row.get('i'), 30, field='row.i')
            for ticket in row['s']:
                if not isinstance(ticket, dict):
                    raise ProviderError('TICKET_SCHEMA', 'Некорректное место tickets.')
                seat_number = short_text(ticket.get('i'), 30, field='seat.i')
                key = (sector_name, row_name, seat_number)
                if key in labels:
                    raise ProviderError('TICKET_SCHEMA', 'Источник вернул одно место дважды.')
                labels.add(key)
                x = _number(ticket.get('x'), field='ticket.x')
                y = _number(ticket.get('y'), field='ticket.y')
                pixel = (x, y)
                if pixel not in point_set:
                    raise ProviderError('TICKET_LAYOUT_MISMATCH',
                                        f'Место {sector_name}/{row_name}/{seat_number} отсутствует в coordinates.')
                if pixel in used_points:
                    raise ProviderError('TICKET_LAYOUT_MISMATCH', 'Два билета указывают на одну точку схемы.')
                used_points.add(pixel)
                compact = ticket.get('k')
                if not isinstance(compact, dict):
                    raise ProviderError('TICKET_SCHEMA', 'У места отсутствует ticket payload.')
                if external_id(compact.get('e')) != expected_date:
                    raise ProviderError('TICKET_SCHEMA', 'Билет относится к другой дате мероприятия.')
                if str(compact.get('x')) != seat_number or str(compact.get('y')) != sector_name or str(compact.get('z')) != row_name:
                    raise ProviderError('TICKET_LAYOUT_MISMATCH', 'Подписи места не совпадают внутри ticket payload.')
                currency = str(ticket.get('cr') or 'RUB').upper()
                if currency != 'RUB':
                    raise ProviderError('TICKET_SCHEMA', 'MVP поддерживает только RUB.')
                result.append({
                    'sector': sector_name,
                    'row': row_name,
                    'number': seat_number,
                    'x': round(x / layout['width'], 6),
                    'y': round(y / layout['height'], 6),
                    'pixel_x': x,
                    'pixel_y': y,
                    'external_ticket_id': str(ticket.get('d') or '')[:100],
                    'source_price_minor': money_minor(ticket.get('p'), field='ticket.p'),
                    'currency': currency,
                    'source_code': str(compact.get('s') or '')[:50],
                })
    if sum(item['capacity'] for item in sectors) != len(layout['points']):
        raise ProviderError('TICKET_LAYOUT_MISMATCH', 'Вместимость секторов не совпадает с количеством точек coordinates.')
    return {'seats': result, 'sectors': sectors}


def normalize_standing_tickets(payload, *, event_date_id):
    """Standing/general-admission data stays separate from Seat.

    The captured example is a 'Парковка' group with count=200. It is therefore
    imported disabled and never converted into 200 synthetic Seat rows.
    """
    if not isinstance(payload, list):
        raise ProviderError('STANDING_SCHEMA', 'Неизвестная структура standing_tickets.')
    expected_date = external_id(event_date_id)
    result = []
    for row in payload:
        if not isinstance(row, dict):
            raise ProviderError('STANDING_SCHEMA', 'Некорректная standing-зона.')
        fragment = row.get('fragment') if isinstance(row.get('fragment'), dict) else {}
        attributes = fragment.get('attributes') if isinstance(fragment.get('attributes'), dict) else {}
        name = text(attributes.get('sector') or attributes.get('label'), 200)
        if not name:
            raise ProviderError('STANDING_SCHEMA', 'У standing-зоны нет названия.')
        count = row.get('count')
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ProviderError('STANDING_SCHEMA', 'Некорректное количество standing-билетов.')
        tickets = row.get('tickets')
        if not isinstance(tickets, list):
            raise ProviderError('STANDING_SCHEMA', 'Некорректный tickets standing-зоны.')
        source_code = ''
        for ticket in tickets:
            compact = ticket.get('k') if isinstance(ticket, dict) else None
            if not isinstance(compact, dict) or external_id(compact.get('e')) != expected_date:
                raise ProviderError('STANDING_SCHEMA', 'Standing-билет относится к другой дате.')
            source_code = source_code or str(compact.get('s') or '')[:50]
        identity = json.dumps({
            'name': name,
            'ticket_type': row.get('ticket_type'),
            'view_scope_type': row.get('view_scope_type'),
            'source_code': source_code,
            'category_id': attributes.get('category_id'),
            'sector_id': attributes.get('sector_id'),
        }, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        result.append({
            'external_key': hashlib.sha256(identity.encode()).hexdigest(),
            'name': name,
            'external_ticket_id': str(row.get('id') or '')[:100],
            'source_price_minor': money_minor(row.get('price'), field='standing.price'),
            'currency': 'RUB',
            'available_count': count,
            'source_code': source_code,
        })
    return result


SENSITIVE = {'password', 'passwd', 'token', 'access_token', 'refresh_token', 'secret',
             'authorization', 'cookie', 'email', 'phone', 'passport', 'snils', 'seller', 'customer'}


def redact(value, depth=0):
    if depth > 25:
        return '[depth limit]'
    if isinstance(value, dict):
        return {str(k): ('[redacted]' if any(word in str(k).lower() for word in SENSITIVE)
                         else redact(v, depth + 1)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, depth + 1) for v in value]
    return value


def structure(value, *, depth=0):
    if depth > 4:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): structure(v, depth=depth + 1) for k, v in list(value.items())[:40]}
    if isinstance(value, list):
        return {'type': 'list', 'length': len(value), 'first': structure(value[0], depth=depth + 1) if value else None}
    return type(value).__name__
