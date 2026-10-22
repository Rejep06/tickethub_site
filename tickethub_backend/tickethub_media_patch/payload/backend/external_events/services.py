"""PortalBilet import into existing Tickethub models.

The verified provider data is read-only. Geometry and external availability are
imported, but TicketUnit is NEVER created automatically: PortalBilet has no
verified HOLD/ORDER capability here, so local locks cannot reserve upstream stock.
"""
from contextlib import contextmanager
from datetime import timedelta
import hashlib
import json
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from core.errors import require
from events.models import Category, Event
from events.services import save_event
from venues.models import Venue, SeatingPlan, Seat
from .models import (
    ExternalEvent, ExternalDate, ExternalSnapshot,
    ExternalSeatInventory, ExternalStandingInventory,
)
from .http import JSONClient, ProviderError
from .normalization import (
    bootstrap, dates_list, external_id, parse_date, structure, redact,
    normalize_layout, normalize_assigned_tickets, normalize_standing_tickets,
)
from .provider import PortalBiletProvider, parse_event_url


def provider_client():
    return PortalBiletProvider(JSONClient(
        timeout=settings.PORTALBILET_HTTP_TIMEOUT,
        max_bytes=settings.PORTALBILET_MAX_RESPONSE_BYTES,
        budget_seconds=settings.PORTALBILET_IMPORT_BUDGET,
    ))


@contextmanager
def source_lock(key):
    """PostgreSQL advisory lock without holding an SQL transaction during HTTP."""
    value = int.from_bytes(hashlib.sha256(('tickethub-import:' + key).encode()).digest()[:8], 'big', signed=True)
    require(connection.vendor == 'postgresql', 'POSTGRES_REQUIRED', 'Импорту нужна PostgreSQL.', status=503)
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [value])
        acquired = cursor.fetchone()[0]
    require(acquired, 'IMPORT_IN_PROGRESS', 'Это событие уже импортируется. Повторите после завершения.')
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s)', [value])


def warning(code, message, resource=None):
    result = {'code': code, 'message': message}
    if resource:
        result['resource'] = resource
    return result


def store_snapshot(source, name, response):
    body = redact(response.payload)
    if len(json.dumps(body, ensure_ascii=False).encode()) > settings.PORTALBILET_SNAPSHOT_BYTES:
        body = None
    ExternalSnapshot.objects.update_or_create(external_event=source, resource=name, defaults={
        'url': response.url, 'sha256': response.sha256, 'byte_count': response.byte_count,
        'structure': structure(response.payload), 'payload': body,
    })


def read_dates(provider, slug, event_data, warnings):
    try:
        response = provider.fetch_dates(slug)
        return dates_list(response.payload), True, response
    except ProviderError as exc:
        warnings.append(warning(exc.code, str(exc), 'dates'))
        warnings.append(warning('DATES_FALLBACK', 'Использованы даты page-data; исчезнувшие даты не отключаются.'))
        return dates_list(event_data['dates']), False, None


def _country_code(data):
    # Current provider payload has a country name, not ISO alpha-2.
    value = (data.get('country_name') or '').strip().casefold()
    return {'россия': 'RU', 'russia': 'RU'}.get(value, '')


def inspect_url(url, *, provider=None):
    _, slug, canonical = parse_event_url(url)
    provider = provider or provider_client()
    page = provider.fetch_event(canonical)
    data = bootstrap(page.payload)
    warnings = []
    dates, authoritative, _ = read_dates(provider, slug, data, warnings)
    preview = {
        'status': 'PREVIEW', 'url': canonical, 'title': data['title'],
        'venue': {'name': data['place_name'], 'address': data['address'], 'city': data['city']},
        'provider': {key: data[key] for key in ['external_event_id', 'event_source_id', 'external_layout_id']},
        'dates': [{'external_date_id': external_id(row['id']), 'start_at': parse_date(row)} for row in dates],
        'dates_authoritative': authoritative,
        'seats_count': None, 'standing_zones_count': None,
        'supported_mode': 'IMPORT_ONLY', 'warnings': warnings,
    }
    if data['external_layout_id'] and dates:
        try:
            layout_response = provider.fetch_hall_layout(data['external_layout_id'])
            layout = normalize_layout(layout_response.payload, expected_layout_id=data['external_layout_id'])
            ticket_response = provider.fetch_tickets(data['event_source_id'], external_id(dates[0]['id']))
            assigned = normalize_assigned_tickets(ticket_response.payload, event_date_id=dates[0]['id'], layout=layout)
            preview['seats_count'] = len(assigned['seats'])
            preview['layout_points_count'] = len(layout['points'])
            preview['layout_background_url'] = layout['background_url']
        except ProviderError as exc:
            warnings.append(warning(exc.code, str(exc), 'preview-layout'))
    return preview


def venue_from_source(source, data):
    """Reuse by provider place ID; later imports preserve manager-edited text."""
    venue, created = Venue.objects.get_or_create(
        external_provider='portalbilet', external_place_id=source.external_place_id,
        defaults={
            'name_ru': data['place_name'], 'name_en': data['place_name'],
            'city': data['city'], 'country': _country_code(data), 'address': data['address'],
        },
    )
    return venue, created


@transaction.atomic
def apply_metadata(source, data, rows, authoritative, actor, warnings):
    source = ExternalEvent.objects.select_for_update().get(pk=source.pk)
    venue, new_venue = venue_from_source(source, data)
    source.venue = venue
    category, _ = Category.objects.get_or_create(slug='external-review', defaults={
        'name_ru': 'Импортировано — проверить категорию', 'name_en': 'Imported — review category',
        'kind': 'OTHER', 'is_active': False,
    })
    created, updated, seen = [], [], []
    for row in rows:
        date_id = external_id(row['id'])
        seen.append(date_id)
        starts = parse_date(row)
        if starts is None:
            warnings.append(warning('DATE_REQUIRES_REVIEW',
                'Источник прислал время без timezone; дата оставлена как «уточняется» до проверки сотрудником.', date_id))
        binding = source.dates.filter(external_date_id=date_id).select_related('event').first()
        defaults = {
            'title_ru': data['title'], 'title_en': data['title'],
            'description_ru': data['description'], 'description_en': '',
            'venue': venue, 'category': category, 'start_at': starts,
            'date_tba': starts is None, 'sale_deadline': starts - timedelta(hours=2) if starts else None,
        }
        if binding is None:
            event = Event(
                slug=f'{parse_event_url(source.url)[1][:120]}-pb-{source.external_event_id}-{date_id}',
                is_published=False, **defaults,
            )
            event.full_clean()
            event.save()
            binding = ExternalDate.objects.create(
                external_event=source, external_date_id=date_id, event=event,
                source_start_at=starts, last_seen_at=timezone.now(), last_local_version=event.version,
            )
            created.append(str(event.id))
        else:
            event = Event.objects.select_for_update().get(pk=binding.event_id)
            untouched = event.version == binding.last_local_version and not event.is_published
            unused = not event.units.exists() and not event.holds.exists() and not event.orders.exists()
            if untouched and unused:
                changed = any(getattr(event, k) != v for k, v in defaults.items())
                if changed:
                    event = save_event(event, {'expected_version': event.version, **defaults}, actor)
                    updated.append(str(event.id))
                binding.last_local_version = event.version
            else:
                warnings.append(warning('LOCAL_EVENT_PRESERVED',
                    'Локальные изменения события сохранены; данные источника доступны в снимке.', date_id))
            binding.source_active = True
            binding.source_start_at = starts
            binding.last_seen_at = timezone.now()
            binding.save()
    if authoritative:
        disappeared = list(source.dates.exclude(external_date_id__in=seen).filter(source_active=True).select_related('event'))
        for binding in disappeared:
            binding.source_active = False
            binding.save(update_fields=['source_active', 'updated_at'])
            warnings.append(warning('SOURCE_DATE_DISAPPEARED',
                'Дата исчезла из источника. Локальное событие/заказы не удалены.', binding.external_date_id))
    source.last_metadata_sync_at = timezone.now()
    source.save(update_fields=['venue', 'last_metadata_sync_at', 'updated_at'])
    return {'events': created, 'venues': int(new_venue)}, {'events': updated}


@transaction.atomic
def apply_layout(source, layout, sectors, actor, warnings):
    source = ExternalEvent.objects.select_for_update().get(pk=source.pk)
    require(source.venue_id is not None, 'IMPORT_ORDER', 'Сначала должна быть создана площадка.')
    plan = SeatingPlan.objects.select_for_update().filter(
        external_provider='portalbilet', external_layout_id=layout['external_layout_id'],
    ).first()
    created = plan is None
    if created:
        plan = SeatingPlan(
            venue=source.venue,
            name=f'{source.venue.name_ru} · PortalBilet {layout["external_layout_id"]}',
            external_provider='portalbilet', external_layout_id=layout['external_layout_id'],
        )
    elif plan.venue_id != source.venue_id:
        raise ProviderError('LAYOUT_VENUE_MISMATCH', 'Одна внешняя схема связана с двумя разными площадками.')

    geometry_changed = (
        plan.external_width != layout['width'] or plan.external_height != layout['height'] or
        plan.external_background_url != layout['background_url'] or
        plan.external_geometry != layout['points'] or (sectors and plan.external_sectors != sectors)
    )
    if geometry_changed and plan.status != 'DRAFT':
        warnings.append(warning('PUBLISHED_LAYOUT_PRESERVED',
            'Источник изменил геометрию, но опубликованная локальная схема не перезаписана. Создайте новую версию.'))
    else:
        plan.external_width = layout['width']
        plan.external_height = layout['height']
        plan.external_background_url = layout['background_url']
        plan.external_geometry = layout['points']
        if sectors:
            plan.external_sectors = sectors
        plan.external_synced_at = timezone.now()
        if not created and geometry_changed:
            plan.version += 1
        plan.save()

    from venues.import_geometry import materialize_geometry
    plan._geometry_created = materialize_geometry(plan)
    attached = 0
    for binding in source.dates.select_related('event'):
        event = Event.objects.select_for_update().get(pk=binding.event_id)
        if event.seating_plan_id == plan.id:
            continue
        if event.seating_plan_id or event.is_published or event.units.exists() or event.holds.exists() or event.orders.exists():
            warnings.append(warning('LOCAL_PLAN_PRESERVED',
                'Схема локального события уже выбрана и не была заменена импортом.', binding.external_date_id))
            continue
        event = save_event(event, {'expected_version': event.version, 'seating_plan': plan}, actor)
        binding.last_local_version = event.version
        binding.save(update_fields=['last_local_version', 'updated_at'])
        attached += 1
    return plan, created, attached


def _coords_equal(seat, row):
    return float(seat.x) == row['x'] and float(seat.y) == row['y']


@transaction.atomic
def apply_assigned_inventory(binding, plan, decoded, warnings):
    """Enrich existing geometry with verified labels, then update per-date availability."""
    from venues.import_geometry import point_key, materialize_geometry
    now = timezone.now()
    plan = SeatingPlan.objects.select_for_update().get(pk=plan.pk)
    created_count = materialize_geometry(plan)
    seats = list(plan.seats.all())
    by_point = {s.external_point_key: s for s in seats if s.external_point_key}
    by_label = {(s.sector, s.row, s.number): s for s in seats if s.labels_known}
    changed, mapped = [], []
    for row in decoded['seats']:
        key = point_key(row['x'], row['y'])
        label = (row['sector'], row['row'], row['number'])
        seat = by_point.get(key)
        if seat is None:
            warnings.append(warning('SEAT_GEOMETRY_PRESERVED',
                f'Точка {" / ".join(label)} не совпала с сохранённой версией схемы; пропущена.', binding.external_date_id))
            continue
        labelled = by_label.get(label)
        if (labelled is not None and labelled.pk != seat.pk) or (
            seat.labels_known and (seat.sector, seat.row, seat.number) != label
        ):
            # Never move an existing label onto another physical point on a guess.
            warnings.append(warning('SEAT_IDENTITY_CONFLICT',
                f'Источник изменил подпись/координаты {" / ".join(label)}; требуется проверка.', binding.external_date_id))
            continue
        if not seat.labels_known:
            seat.sector, seat.row, seat.number = label
            seat.updated_at = now
            changed.append(seat)
            by_label[label] = seat
        mapped.append((seat, row))
    if changed:
        # Metadata enrichment is allowed even on a published layout: x/y and IDs stay fixed.
        Seat.objects.bulk_update(changed, ['sector', 'row', 'number', 'updated_at'], batch_size=500)
        plan.version += 1
        plan.save(update_fields=['version', 'updated_at'])

    existing_inventory = {item.seat_id: item for item in binding.seat_inventory.all()}
    create_inventory, update_inventory, seen = [], [], set()
    for seat, row in mapped:
        seen.add(seat.id)
        item = existing_inventory.get(seat.id)
        if item is None:
            create_inventory.append(ExternalSeatInventory(
                external_date=binding, seat=seat,
                external_ticket_id=row['external_ticket_id'], source_price_minor=row['source_price_minor'],
                currency=row['currency'], source_code=row['source_code'], source_available=True, last_seen_at=now,
            ))
        else:
            item.external_ticket_id = row['external_ticket_id']
            item.source_price_minor = row['source_price_minor']
            item.currency = row['currency']
            item.source_code = row['source_code']
            item.source_available = True
            item.last_seen_at = item.updated_at = now
            update_inventory.append(item)
    if create_inventory:
        ExternalSeatInventory.objects.bulk_create(create_inventory, batch_size=500)
    if update_inventory:
        ExternalSeatInventory.objects.bulk_update(update_inventory,
            ['external_ticket_id', 'source_price_minor', 'currency', 'source_code', 'source_available', 'last_seen_at', 'updated_at'],
            batch_size=500)
    unavailable = binding.seat_inventory.exclude(seat_id__in=seen).filter(source_available=True).update(
        source_available=False, updated_at=now)
    # Missing tickets mean "not offered by source", not proof of a completed sale.
    return {
        'seats_created': created_count, 'seats_updated': len(changed),
        'inventory_created': len(create_inventory), 'inventory_updated': len(update_inventory),
        'inventory_total': len(mapped), 'inventory_unavailable': unavailable,
    }


@transaction.atomic
def apply_standing_inventory(binding, rows):
    now = timezone.now()
    existing = {item.external_key: item for item in binding.standing_inventory.all()}
    create_rows, update_rows, seen = [], [], set()
    for row in rows:
        key = row['external_key']
        seen.add(key)
        item = existing.get(key)
        if item is None:
            create_rows.append(ExternalStandingInventory(
                external_date=binding, external_key=key, name=row['name'],
                external_ticket_id=row['external_ticket_id'], source_price_minor=row['source_price_minor'],
                currency=row['currency'], source_code=row['source_code'], available_count=row['available_count'],
                source_available=row['available_count'] > 0, last_seen_at=now,
            ))
        else:
            item.name = row['name']
            item.external_ticket_id = row['external_ticket_id']
            item.source_price_minor = row['source_price_minor']
            item.currency = row['currency']
            item.source_code = row['source_code']
            item.available_count = row['available_count']
            item.source_available = row['available_count'] > 0
            item.last_seen_at = now
            update_rows.append(item)
    if create_rows:
        ExternalStandingInventory.objects.bulk_create(create_rows, batch_size=500)
    if update_rows:
        ExternalStandingInventory.objects.bulk_update(update_rows,
            ['name', 'external_ticket_id', 'source_price_minor', 'currency', 'source_code',
             'available_count', 'source_available', 'last_seen_at', 'updated_at'], batch_size=500)
    unavailable = binding.standing_inventory.exclude(external_key__in=seen).filter(source_available=True).update(
        source_available=False, available_count=0, updated_at=now)
    return {'created': len(create_rows), 'updated': len(update_rows), 'total': len(rows), 'unavailable': unavailable}


def import_url(url, actor, *, provider=None):
    _, slug, canonical = parse_event_url(url)
    provider = provider or provider_client()
    with source_lock('url:' + canonical):
        page = provider.fetch_event(canonical)
        data = bootstrap(page.payload)
        with source_lock('portalbilet:' + data['external_event_id']):
            source, _ = ExternalEvent.objects.get_or_create(
                provider='portalbilet', external_event_id=data['external_event_id'],
                defaults={key: data[key] for key in ['event_source_id', 'external_place_id', 'external_layout_id']} |
                         {'url': canonical, 'title': data['title']},
            )
            source.status = 'RUNNING'
            source.last_attempt_at = timezone.now()
            source.url, source.title = canonical, data['title']
            for key in ['event_source_id', 'external_place_id', 'external_layout_id']:
                setattr(source, key, data[key])
            source.save()
            warnings, failed_resources = [], []
            report = {
                'status': 'RUNNING', 'source_id': str(source.pk), 'mode': 'IMPORT_ONLY',
                'created': {'events': [], 'venues': 0, 'plans': 0, 'seats': 0,
                            'seat_inventory': 0, 'standing_inventory': 0, 'ticket_units': 0},
                'updated': {'events': [], 'seats': 0, 'seat_inventory': 0, 'standing_inventory': 0}, 'warnings': warnings, 'resources': {},
                'mapping': {
                    'verified': True,
                    'geometry_join': 'ticket.x/y == coordinates.x/y',
                    'seat_identity': 'layout + normalized point; labels verified by ticket x/y',
                    'ticket_unit_created': False,
                },
            }
            try:
                store_snapshot(source, 'page-data', page)
                rows, authoritative, response = read_dates(provider, slug, data, warnings)
                if response:
                    store_snapshot(source, 'dates', response)
                if len(rows) > settings.PORTALBILET_MAX_DATES:
                    warnings.append(warning('DATE_LIMIT', 'Импортировано только ограниченное число дат; полный список сохранён в снимке.'))
                    rows = rows[:settings.PORTALBILET_MAX_DATES]
                    authoritative = False
                new, updated = apply_metadata(source, data, rows, authoritative, actor, warnings)
                report['created'].update(new)
                report['updated'].update(updated)

                try:
                    prices = provider.fetch_dates_prices(data['event_source_id'])
                    store_snapshot(source, 'dates-prices', prices)
                    report['resources']['dates-prices'] = {'status': 'FETCHED', 'bytes': prices.byte_count, 'sha256': prices.sha256}
                except ProviderError as exc:
                    failed_resources.append('dates-prices')
                    report['resources']['dates-prices'] = {'status': 'FAILED', 'code': exc.code}
                    warnings.append(warning(exc.code, str(exc), 'dates-prices'))

                layout = plan = None
                if data['external_layout_id']:
                    try:
                        response = provider.fetch_hall_layout(data['external_layout_id'])
                        store_snapshot(source, f'coordinates:{data["external_layout_id"]}', response)
                        layout = normalize_layout(response.payload, expected_layout_id=data['external_layout_id'])
                        with source_lock('portalbilet-layout:' + data['external_layout_id']):
                            plan, plan_created, attached = apply_layout(source, layout, [], actor, warnings)
                        report['created']['plans'] = int(plan_created)
                        report['created']['seats'] += plan._geometry_created
                        report['plan_id'] = str(plan.id)
                        report['resources'][f'coordinates:{data["external_layout_id"]}'] = {
                            'status': 'IMPORTED', 'points': len(layout['points']), 'background_url': layout['background_url'],
                        }
                    except ProviderError as exc:
                        failed_resources.append('coordinates')
                        warnings.append(warning(exc.code, str(exc), 'coordinates'))

                sector_geometry_applied = False
                if layout and plan:
                    for row in rows:
                        date_id = external_id(row['id'])
                        binding = source.dates.get(external_date_id=date_id)
                        try:
                            response = provider.fetch_tickets(data['event_source_id'], date_id)
                            store_snapshot(source, f'tickets:{date_id}', response)
                            decoded = normalize_assigned_tickets(response.payload, event_date_id=date_id, layout=layout)
                            if not sector_geometry_applied:
                                with source_lock('portalbilet-layout:' + data['external_layout_id']):
                                    plan, _, _ = apply_layout(source, layout, decoded['sectors'], actor, warnings)
                                sector_geometry_applied = True
                                report['created']['seats'] += plan._geometry_created
                            counts = apply_assigned_inventory(binding, plan, decoded, warnings)
                            report['created']['seats'] += counts['seats_created']
                            report['updated']['seats'] += counts['seats_updated']
                            report['created']['seat_inventory'] += counts['inventory_created']
                            report['updated']['seat_inventory'] += counts['inventory_updated']
                            report['resources'][f'tickets:{date_id}'] = {
                                'status': 'IMPORTED', 'available_seats': len(decoded['seats']),
                                'sectors': len(decoded['sectors']),
                            }
                        except ProviderError as exc:
                            failed_resources.append(f'tickets:{date_id}')
                            report['resources'][f'tickets:{date_id}'] = {'status': 'FAILED', 'code': exc.code}
                            warnings.append(warning(exc.code, str(exc), f'tickets:{date_id}'))

                        try:
                            response = provider.fetch_standing_tickets(data['event_source_id'], date_id)
                            store_snapshot(source, f'standing:{date_id}', response)
                            standing = normalize_standing_tickets(response.payload, event_date_id=date_id)
                            standing_counts = apply_standing_inventory(binding, standing)
                            report['created']['standing_inventory'] += standing_counts['created']
                            report['updated']['standing_inventory'] += standing_counts['updated']
                            report['resources'][f'standing:{date_id}'] = {
                                'status': 'IMPORTED', 'groups': len(standing),
                                'available_count': sum(item['available_count'] for item in standing),
                            }
                        except ProviderError as exc:
                            failed_resources.append(f'standing:{date_id}')
                            report['resources'][f'standing:{date_id}'] = {'status': 'FAILED', 'code': exc.code}
                            warnings.append(warning(exc.code, str(exc), f'standing:{date_id}'))

                if plan:
                    report['geometry'] = {
                        'total_seats': plan.seats.count(),
                        'labels_unknown': plan.seats.filter(sector='', row='', number='').count(),
                        'source_points': len(plan.external_geometry),
                    }
                warnings.extend([
                    warning('DRAFT_REVIEW_REQUIRED',
                        'События остаются непубличными. Проверьте категорию, EN-текст, дату/timezone, Fan ID и правила возврата.'),
                    warning('READ_ONLY_SOURCE',
                        'PortalBilet импортируется как read-only источник. Локальный hold не резервирует место у PortalBilet.'),
                    warning('LOCAL_STOCK_NOT_CREATED',
                        'External inventory связан со схемой, но собственные TicketUnit автоматически не создаются.'),
                ])
                report['status'] = 'PARTIAL' if failed_resources else 'COMPLETED'
            except ProviderError as exc:
                report['status'] = 'PARTIAL' if report['created']['events'] else 'FAILED'
                warnings.append(warning(exc.code, str(exc)))
            except Exception:
                source.status = 'FAILED'
                source.diagnostics = {**report, 'status': 'FAILED', 'error_code': 'IMPORT_INTERNAL_ERROR'}
                source.save(update_fields=['status', 'diagnostics', 'updated_at'])
                raise
            source.status = report['status']
            source.diagnostics = report
            source.save(update_fields=['status', 'diagnostics', 'updated_at'])
            return report


def sync_source(source_id, actor, *, provider=None):
    source = get_object_or_404(ExternalEvent, pk=source_id)
    return import_url(source.url, actor, provider=provider)
