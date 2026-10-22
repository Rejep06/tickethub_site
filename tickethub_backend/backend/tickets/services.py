from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from core.errors import require, check_version
from events.models import Event
from events.services import check_orderable
from users.models import User
from .models import CheckoutHold, CheckoutHoldItem, TicketOffer, TicketUnit


def valid_stock(unit, until):
    return unit.stock_basis == 'OWNED' or (unit.allocation_until is not None and unit.allocation_until >= until)


def checkout_deadline(event, now):
    from events.checkout_policy import hold_deadline
    return hold_deadline(event, now, settings.HOLD_SECONDS)


def available_units(event, now=None, *, for_hold=None, until=None, require_price=True):
    now = now or timezone.now()
    until = until or checkout_deadline(event, now)
    states = Q(status='AVAILABLE') | Q(status='CHECKOUT_HELD', current_hold__status='ACTIVE', current_hold__expires_at__lte=now)
    if for_hold:
        states |= Q(status='CHECKOUT_HELD', current_hold=for_hold)
    stock = Q(stock_basis='OWNED') | Q(stock_basis='EXCLUSIVE_ALLOCATION', allocation_until__gte=until)
    # Real AVAILABLE inventory wins over the legacy offer REQUEST flag. No
    # inventory / unknown price still leads to a request, never invented tickets.
    labels = Q(seat__isnull=True) | (~Q(seat__sector='') & ~Q(seat__row='') & ~Q(seat__number=''))
    queryset = TicketUnit.objects.filter(states, stock, labels, event=event, offer__is_active=True).exclude(order_items__is_active=True)
    # A manager's Quote supplies its own price. Public direct checkout does not.
    return queryset.filter(offer__sale_price_minor__gt=0) if require_price else queryset


def release_event_holds_locked(event, status, *, expired_only=False):
    now = timezone.now()
    qs = CheckoutHold.objects.select_for_update().filter(event=event, status='ACTIVE').order_by('id')
    if expired_only:
        qs = qs.filter(expires_at__lte=now)
    holds = list(qs)
    for hold in holds:
        _release_hold_locked(hold, status, now)
    return len(holds)


def _release_hold_locked(hold, status, now):
    # Only the pointer to this still-active checkout is released, never OrderItems.
    units = TicketUnit.objects.select_for_update().filter(current_hold=hold, status='CHECKOUT_HELD').order_by('id')
    for unit in units:
        unit.current_hold = None
        unit.status = 'AVAILABLE' if valid_stock(unit, now + timedelta(seconds=settings.HOLD_SECONDS)) else 'BLOCKED'
        unit.version += 1
        unit.save(update_fields=['current_hold', 'status', 'version', 'updated_at'])
    hold.status = status
    hold.save(update_fields=['status', 'updated_at'])


def _normalize_selection(selection):
    if selection['mode'] == 'SEATS':
        return {'mode': 'SEATS', 'seat_ids': sorted(str(x) for x in selection['seat_ids'])}
    return {'mode': 'CATEGORY', 'offer_id': str(selection['offer_id']), 'quantity': selection['quantity']}


def _select_units(event, selection, now, *, old_hold=None, until=None, lock=False):
    queryset = available_units(event, now, for_hold=old_hold, until=until).select_related('offer', 'seat').order_by('id')
    if lock:
        queryset = queryset.select_for_update(of=('self',))
    if selection['mode'] == 'SEATS':
        require(event.seating_plan_id is not None, 'INVALID_SELECTION', 'У события нет схемы.')
        ids = selection['seat_ids']
        require(0 < len(ids) <= settings.DIRECT_ORDER_LIMIT and len(set(ids)) == len(ids), 'INVALID_SELECTION', 'Проверьте количество мест.')
        units = list(queryset.filter(seat_id__in=ids))
        require(len(units) == len(ids), 'SEAT_UNAVAILABLE', 'Одно из мест больше недоступно.')
    else:
        require(event.seating_plan_id is None, 'INVALID_SELECTION', 'Для этого события выберите конкретные места.')
        count = selection['quantity']
        require(0 < count <= settings.DIRECT_ORDER_LIMIT, 'INVALID_SELECTION', 'Проверьте количество билетов.')
        units = list(queryset.filter(offer_id=selection['offer_id'], seat__isnull=True)[:count])
        require(len(units) == count, 'INSUFFICIENT_STOCK', 'Недостаточно билетов выбранной категории.')
    require(all(u.offer.sale_price_minor and u.offer.sale_price_minor > 0 for u in units), 'PRICE_CHANGED', 'Проверьте цену.')
    return units


def preview(event_id, selection):
    event = get_object_or_404(Event, pk=event_id, is_published=True, visibility='PUBLIC')
    now = timezone.now()
    check_orderable(event, now)
    units = _select_units(event, _normalize_selection(selection), now)
    return {'event_id': event.id, 'total_minor': sum(u.offer.sale_price_minor for u in units), 'currency': 'RUB',
            'event_version': event.version, 'offer_versions': {str(u.offer_id): u.offer.version for u in units},
            'items': [public_unit(u, u.offer.sale_price_minor) for u in units], 'server_now': now}


def public_unit(unit, price):
    return {'offer_id': unit.offer_id, 'seat_id': unit.seat_id,
            'name_ru': unit.offer.name_ru, 'name_en': unit.offer.name_en,
            'sector': unit.seat.sector if unit.seat_id else '', 'row': unit.seat.row if unit.seat_id else '',
            'seat_number': unit.seat.number if unit.seat_id else '', 'sale_price_minor': price}


@transaction.atomic
def create_hold(user, event_id, selection, expected_total_minor, expected_offer_versions=None, *, quote_id=None, idempotency_key=None):
    # Customer lock serializes repeated requests across events. Staff operations
    # never acquire a User lock after Event, so the lock order remains acyclic.
    User.objects.select_for_update().get(pk=user.pk)
    from core.models import IdempotencyRecord
    from core.validation import fingerprint
    digest = fingerprint({'event_id': event_id, 'selection': selection, 'expected_total_minor': expected_total_minor,
                          'expected_offer_versions': expected_offer_versions, 'quote_id': quote_id})
    if idempotency_key:
        replay = IdempotencyRecord.objects.filter(user=user, key=idempotency_key).first()
        if replay:
            require(replay.request_hash == digest, 'IDEMPOTENCY_CONFLICT', 'Ключ уже использован для другого выбора.')
            return replay.hold
    def remember(hold):
        if idempotency_key:
            IdempotencyRecord.objects.create(user=user, key=idempotency_key, request_hash=digest, hold=hold)
        return hold
    event = get_object_or_404(Event.objects.select_for_update(), pk=event_id)
    now = timezone.now()  # Read after waiting for locks.
    check_orderable(event, now, from_quote=bool(quote_id))
    from orders.models import Order
    active_order = Order.objects.filter(user=user, event=event, order_state__in=['NEW', 'IN_PROGRESS']).first()
    require(active_order is None, 'ORDER_EXISTS', 'Заказ по этому событию уже ожидает обработки.',
            details={'order_id': str(active_order.pk)} if active_order else {})
    release_event_holds_locked(event, 'EXPIRED', expired_only=True)
    old = CheckoutHold.objects.select_for_update().filter(user=user, event=event, status='ACTIVE').first()
    expires = min(old.expires_at, checkout_deadline(event, now)) if old else checkout_deadline(event, now)
    quote = None
    if quote_id:
        from ticket_requests.models import Quote
        quote = get_object_or_404(Quote.objects.select_for_update(), pk=quote_id, ticket_request__user=user)
        require(quote.event_id == event.id and quote.status == 'SENT', 'QUOTE_UNAVAILABLE', 'Предложение недоступно.')
        require(quote.expires_at >= expires, 'QUOTE_EXPIRED', 'Предложение истекло или скоро истечёт.')
        require(quote.ticket_request.status in ['OFFERED', 'IN_PROGRESS'], 'QUOTE_UNAVAILABLE', 'Заявка закрыта.')
        normalized = {'mode': 'QUOTE', 'quote_id': str(quote.id)}
    else:
        require(event.is_published and event.visibility == 'PUBLIC', 'NOT_FOUND', 'Событие не найдено.', status=404)
        normalized = _normalize_selection(selection)
    if old and old.selection == normalized and old.quote_id == quote_id:
        return remember(old)
    require(expires > now, 'SALES_CLOSED', 'Время оформления на это мероприятие истекло.')
    if quote:
        quote_items = list(quote.items.all())
        units = list(available_units(event, now, for_hold=old, until=expires, require_price=False)
                     .select_for_update(of=('self',)).select_related('offer', 'seat')
                     .filter(id__in=[i.ticket_unit_id for i in quote_items]).order_by('id'))
        require(len(units) == len(quote_items) and len(units) > 0, 'SEAT_UNAVAILABLE', 'Наличие по предложению изменилось.')
        prices = {i.ticket_unit_id: i.price_minor for i in quote_items}
    else:
        units = _select_units(event, normalized, now, old_hold=old, until=expires, lock=True)
        prices = {u.id: u.offer.sale_price_minor for u in units}
    total = sum(prices.values())
    require(total == expected_total_minor, 'PRICE_CHANGED', 'Цена изменилась. Повторите расчёт.', details={'total_minor': total})
    if expected_offer_versions is not None and not quote:
        require(all(expected_offer_versions.get(str(u.offer_id)) == u.offer.version for u in units),
                'PRICE_CHANGED', 'Предложение изменилось. Повторите расчёт.')
    if old:
        # Failed replacement rolls back the release and preserves the old selection.
        _release_hold_locked(old, 'RELEASED', now)
        old.items.all().delete()
        hold = old
        hold.status = 'ACTIVE'
        hold.quote = quote
        hold.selection = normalized
        hold.total_minor = total
        hold.event_version = event.version
        hold.expires_at = expires
        hold.save()
    else:
        hold = CheckoutHold.objects.create(user=user, event=event, quote=quote, expires_at=expires,
                                           selection=normalized, total_minor=total, event_version=event.version)
    for unit in units:
        unit.current_hold = hold
        unit.status = 'CHECKOUT_HELD'
        unit.version += 1
        unit.save(update_fields=['current_hold', 'status', 'version', 'updated_at'])
        CheckoutHoldItem.objects.create(hold=hold, ticket_unit=unit,
                                       name_ru=unit.offer.name_ru, name_en=unit.offer.name_en,
                                       sector=unit.seat.sector if unit.seat_id else '',
                                       row=unit.seat.row if unit.seat_id else '',
                                       seat_number=unit.seat.number if unit.seat_id else '', sale_price_minor=prices[unit.id])
    return remember(hold)


@transaction.atomic
def release_hold(user, hold_id):
    User.objects.select_for_update().get(pk=user.pk)
    initial = get_object_or_404(CheckoutHold, pk=hold_id, user=user)
    Event.objects.select_for_update().get(pk=initial.event_id)
    hold = CheckoutHold.objects.select_for_update().get(pk=hold_id)
    if hold.status in ['RELEASED', 'EXPIRED']:
        return hold
    require(hold.status == 'ACTIVE', 'HOLD_CONVERTED', 'Резерв уже закреплён за заказом.')
    now = timezone.now()
    _release_hold_locked(hold, 'EXPIRED' if hold.expires_at <= now else 'RELEASED', now)
    return hold


def cleanup_expired_holds():
    ids = CheckoutHold.objects.filter(status='ACTIVE', expires_at__lte=timezone.now()).values_list('event_id', flat=True).distinct()
    count = 0
    for event_id in list(ids):
        with transaction.atomic():
            event = Event.objects.select_for_update().get(pk=event_id)
            count += release_event_holds_locked(event, 'EXPIRED', expired_only=True)
    return count


@transaction.atomic
def save_offer(instance, data):
    expected = data.pop('expected_version', None)
    event_id = instance.event_id if instance else data['event'].pk
    Event.objects.select_for_update().get(pk=event_id)
    offer = TicketOffer.objects.select_for_update().get(pk=instance.pk) if instance else TicketOffer()
    if instance:
        check_version(offer, expected)
        require('event' not in data or data['event'].pk == offer.event_id, 'INVALID_CHANGE', 'Событие неизменяемо.')
    for key, value in data.items():
        setattr(offer, key, value)
    offer.full_clean()
    if instance:
        offer.version += 1
    offer.save()
    return offer


@transaction.atomic
def save_unit(instance, data):
    expected = data.pop('expected_version', None)
    event_id = instance.event_id if instance else data['event'].pk
    Event.objects.select_for_update().get(pk=event_id)
    unit = TicketUnit.objects.select_for_update().get(pk=instance.pk) if instance else TicketUnit()
    if instance:
        check_version(unit, expected)
        require(unit.status in ['AVAILABLE', 'BLOCKED'], 'UNIT_OCCUPIED', 'Занятый билет нельзя редактировать.')
        require('event' not in data or data['event'].pk == unit.event_id, 'INVALID_CHANGE', 'Событие неизменяемо.')
        if unit.hold_items.exists() or unit.order_items.exists():
            for field in ['offer', 'seat', 'supplier']:
                if field in data:
                    require(getattr(data[field], 'pk', None) == getattr(unit, field + '_id'), 'INVALID_CHANGE', 'Идентичность использованного билета неизменяема.')
    for key, value in data.items():
        setattr(unit, key, value)
    unit.full_clean()
    if not valid_stock(unit, timezone.now() + timedelta(seconds=settings.HOLD_SECONDS)):
        unit.status = 'BLOCKED'
    if instance:
        unit.version += 1
    unit.save()
    return unit


@transaction.atomic
def set_unit_blocked(unit_id, expected_version, blocked, reason, confirmed_valid=False):
    initial = get_object_or_404(TicketUnit, pk=unit_id)
    Event.objects.select_for_update().get(pk=initial.event_id)
    unit = TicketUnit.objects.select_for_update().get(pk=unit_id)
    check_version(unit, expected_version)
    require(reason.strip(), 'REASON_REQUIRED', 'Укажите причину.', status=400)
    require(unit.status in ['AVAILABLE', 'BLOCKED'] and not unit.order_items.filter(is_active=True).exists(),
            'UNIT_OCCUPIED', 'Сначала урегулируйте действующий заказ или резерв.')
    if not blocked:
        require(confirmed_valid and valid_stock(unit, timezone.now() + timedelta(seconds=settings.HOLD_SECONDS)),
                'STOCK_NOT_CONFIRMED', 'Подтвердите пригодность и наличие билета.')
    unit.status = 'BLOCKED' if blocked else 'AVAILABLE'
    unit.internal_notes = reason
    unit.version += 1
    unit.save(update_fields=['status', 'internal_notes', 'version', 'updated_at'])
    return unit


@transaction.atomic
def renew_supplier_allocation(unit_id, actor, expected_version, allocation_until, reason, confirmed_valid):
    initial = get_object_or_404(TicketUnit.objects.only('event_id'), pk=unit_id)
    Event.objects.select_for_update().get(pk=initial.event_id)
    unit = TicketUnit.objects.select_for_update().get(pk=unit_id)
    check_version(unit, expected_version)
    require(unit.stock_basis == 'EXCLUSIVE_ALLOCATION', 'INVALID_STOCK_BASIS', 'Это не закрепление поставщика.')
    require(confirmed_valid and reason.strip(), 'STOCK_NOT_CONFIRMED', 'Нужны подтверждение и основание.', status=400)
    require(allocation_until > timezone.now() + timedelta(seconds=settings.HOLD_SECONDS)
            and (unit.allocation_until is None or allocation_until > unit.allocation_until),
            'INVALID_DEADLINE', 'Разрешено только продлить подтверждённое закрепление.', status=400)
    unit.allocation_until = allocation_until
    unit.internal_notes = reason
    unit.version += 1
    # Renewal alone does not approve a previously returned/blocked ticket for resale.
    unit.save(update_fields=['allocation_until', 'internal_notes', 'version', 'updated_at'])
    from orders.services import add_history, touch_order
    from orders.models import Order
    for order in Order.objects.select_for_update().filter(items__ticket_unit=unit, items__is_active=True):
        touch_order(order)
        add_history(order, 'SUPPLIER_ALLOCATION_RENEWED', '', actor,
                    f'Unit {unit.id}, until {allocation_until.isoformat()}. {reason}')
    return unit
