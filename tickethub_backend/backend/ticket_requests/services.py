from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from core.consents import accept_documents
from core.email import notify, notify_staff
from core.errors import require, check_version
from core.validation import fingerprint
from events.models import Event
from orders.services import require_customer_profile, _repeat
from tickets.models import TicketUnit, CheckoutHold
from tickets.services import available_units, _release_hold_locked, create_hold
from users.models import User
from .models import TicketRequest, Quote, QuoteItem


def _lock_request(request_id, additional_event_id=None):
    initial = get_object_or_404(TicketRequest, pk=request_id)
    # Same customer-first order as checkout; then events sorted, then Request.
    # It also serializes proposals for an as-yet unlisted event.
    User.objects.select_for_update().get(pk=initial.user_id)
    event_ids = set(initial.quotes.values_list('event_id', flat=True))
    if initial.event_id:
        event_ids.add(initial.event_id)
    if additional_event_id:
        event_ids.add(additional_event_id)
    list(Event.objects.select_for_update().filter(pk__in=event_ids).order_by('id'))
    return TicketRequest.objects.select_for_update().get(pk=request_id)


@transaction.atomic
def create_ticket_request(user, data, idempotency_key, analytics_session_key=''):
    user = User.objects.select_for_update().get(pk=user.pk)
    digest = fingerprint(data)
    existing = _repeat(TicketRequest.objects.filter(user=user, idempotency_key=idempotency_key).first(), digest)
    if existing:
        return existing, False
    require(settings.PUBLIC_FORMS_ENABLED, 'FORMS_DISABLED', 'Приём новых заявок временно закрыт.', status=503)
    require_customer_profile(user)
    event = None
    if data.get('event_id'):
        event = get_object_or_404(Event, pk=data['event_id'], is_published=True, visibility='PUBLIC')
    require(event or data.get('custom_event_name', '').strip() or data.get('comment', '').strip(),
            'EVENT_REQUIRED', 'Опишите нужное мероприятие.', status=400)
    require(1 <= data['quantity'] <= settings.REQUEST_LIMIT, 'INVALID_QUANTITY', 'Проверьте количество.', status=400)
    accept_documents(user, data.get('accepted_documents', {}), 'REQUEST')
    request = TicketRequest.objects.create(user=user, event=event, quantity=data['quantity'],
        custom_event_name=data.get('custom_event_name', ''), city=data.get('city', ''),
        desired_date=data.get('desired_date'), preferences=data.get('preferences', ''),
        together_required=data.get('together_required', False), budget_minor=data.get('budget_minor'),
        comment=data.get('comment', ''), customer_name=user.name, customer_email=user.email,
        customer_phone=user.phone, idempotency_key=idempotency_key, request_hash=digest,
        analytics_session_key=analytics_session_key)
    from analytics.services import record_request_event
    record_request_event(request, 'REQUEST_CREATED')
    notify_staff(f'Новая заявка {request.number}', request.id)
    body = 'Заявка получена. Менеджер подберёт варианты.' if user.locale == 'ru' else 'Request received. A manager will look for suitable tickets.'
    notify(user.email, f'Tickethub {request.number}', body, request.id)
    return request, True


def _withdraw_quote_locked(quote):
    for hold in CheckoutHold.objects.select_for_update().filter(quote=quote, status='ACTIVE').order_by('id'):
        _release_hold_locked(hold, 'RELEASED', timezone.now())
    quote.status = 'WITHDRAWN'
    quote.save(update_fields=['status', 'updated_at'])


@transaction.atomic
def change_request(request_id, actor, data, *, customer=False):
    if customer:
        get_object_or_404(TicketRequest, pk=request_id, user=actor)
    request = _lock_request(request_id, data.get('event_id'))
    check_version(request, data.pop('expected_version'))
    require(request.status not in ['CONVERTED', 'CANCELLED', 'REJECTED'], 'REQUEST_CLOSED', 'Заявка закрыта.')
    new_status = data.pop('status', request.status)
    if customer:
        require(new_status == 'CANCELLED', 'INVALID_TRANSITION', 'Клиент может только отменить заявку.', status=400)
    else:
        require(new_status in ['IN_PROGRESS', 'CANCELLED', 'REJECTED', request.status], 'INVALID_TRANSITION', 'Недопустимый переход.')
    if 'manager_id' in data:
        request.manager = get_object_or_404(User, pk=data.pop('manager_id'), is_active=True, is_staff=True,
                                           staff_role__in=['ADMIN', 'MANAGER'])
    if 'event_id' in data:
        require(not request.quotes.exists(), 'QUOTE_EXISTS', 'Нельзя менять привязку после создания предложения.')
        request.event = get_object_or_404(Event, pk=data.pop('event_id'))
    for key, value in data.items():
        setattr(request, key, value)
    if new_status == 'IN_PROGRESS':
        request.manager = request.manager or actor
    if new_status in ['CANCELLED', 'REJECTED']:
        for quote in request.quotes.filter(status__in=['DRAFT', 'SENT']):
            _withdraw_quote_locked(quote)
    request.status = new_status
    request.version += 1
    request.save()
    if new_status == 'IN_PROGRESS':
        from analytics.services import record_request_event
        record_request_event(request, 'REQUEST_PROCESSING_STARTED')
    return request


@transaction.atomic
def create_quote(request_id, actor, data):
    request = _lock_request(request_id, data['event_id'])
    check_version(request, data['expected_version'])
    require(request.status in ['NEW', 'IN_PROGRESS', 'OFFERED'], 'REQUEST_CLOSED', 'Заявка закрыта.')
    event = get_object_or_404(Event, pk=data['event_id'])
    require(event.status == 'SCHEDULED', 'EVENT_NOT_ORDERABLE', 'Проверьте статус события.')
    require(timezone.now() + timedelta(seconds=settings.HOLD_SECONDS) < data['expires_at'],
            'INVALID_EXPIRY', 'Срок предложения слишком короткий.', status=400)
    require(event.sale_deadline and data['expires_at'] <= event.sale_deadline, 'INVALID_EXPIRY', 'Предложение не может действовать после закрытия продаж.', status=400)
    payload = data['items']
    ids = [item['ticket_unit_id'] for item in payload]
    require(len(ids) == len(set(ids)) and 0 < len(ids) <= settings.REQUEST_LIMIT,
            'INVALID_ITEMS', 'Проверьте количество билетов.', status=400)
    units = {u.id: u for u in available_units(event, require_price=False).filter(pk__in=ids).select_related('seat', 'offer')}
    require(len(units) == len(ids), 'SEAT_UNAVAILABLE', 'Предлагать можно только подтверждённое наличие.')
    if request.together_required:
        require(data.get('together_confirmed', False), 'ADJACENCY_NOT_CONFIRMED', 'Подтвердите выполнение обязательного условия мест рядом.')
        seats = [unit.seat for unit in units.values() if unit.seat_id]
        mapped = len(seats) == len(units) and all(seat.adjacency_group and seat.adjacency_position is not None for seat in seats)
        if mapped:
            positions = sorted(seat.adjacency_position for seat in seats)
            require(len({seat.adjacency_group for seat in seats}) == 1 and positions == list(range(positions[0], positions[0] + len(positions))),
                    'ADJACENCY_MISMATCH', 'Разметка показывает, что выбранные места не соседние.')
        else:
            require(bool(data.get('public_comment', '').strip()), 'ADJACENCY_NOT_CONFIRMED', 'Опишите клиенту вручную проверенное размещение.')
    # A new draft is a new explicit version; previously sent prices remain historical.
    version = (request.quotes.aggregate(n=Max('version'))['n'] or 0) + 1
    quote = Quote.objects.create(ticket_request=request, event=event, version=version,
                                  expires_at=data['expires_at'], public_comment=data.get('public_comment', ''),
                                  total_minor=sum(item['price_minor'] for item in payload), together_confirmed=data.get('together_confirmed', False))
    for item in payload:
        unit = units[item['ticket_unit_id']]
        QuoteItem.objects.create(quote=quote, ticket_unit=unit, price_minor=item['price_minor'],
                                 name_ru=unit.offer.name_ru, name_en=unit.offer.name_en,
                                 sector=unit.seat.sector if unit.seat_id else '', row=unit.seat.row if unit.seat_id else '',
                                 seat_number=unit.seat.number if unit.seat_id else '')
    request.manager = request.manager or actor
    if request.status == 'NEW':
        request.status = 'IN_PROGRESS'
    request.version += 1
    request.save()
    return quote


@transaction.atomic
def send_quote(quote_id, actor, expected_version):
    initial = get_object_or_404(Quote, pk=quote_id)
    request = _lock_request(initial.ticket_request_id, initial.event_id)
    check_version(request, expected_version)
    quote = Quote.objects.select_for_update().get(pk=quote_id)
    require(request.status in ['IN_PROGRESS', 'OFFERED'] and quote.status == 'DRAFT', 'INVALID_TRANSITION', 'Нельзя отправить это предложение.')
    require(quote.expires_at > timezone.now() + timedelta(seconds=settings.HOLD_SECONDS), 'QUOTE_EXPIRED', 'Предложение скоро истечёт.')
    ids = list(quote.items.values_list('ticket_unit_id', flat=True))
    require(bool(ids) and available_units(quote.event, require_price=False).filter(pk__in=ids).count() == len(ids), 'SEAT_UNAVAILABLE', 'Проверьте актуальное наличие.')
    for previous in request.quotes.filter(status='SENT').exclude(pk=quote.id):
        _withdraw_quote_locked(previous)
    quote.status, quote.sent_at = 'SENT', timezone.now()
    quote.save(update_fields=['status', 'sent_at', 'updated_at'])
    request.status = 'OFFERED'
    request.version += 1
    request.save(update_fields=['status', 'version', 'updated_at'])
    from analytics.services import record_request_event
    record_request_event(request, 'QUOTE_SENT')
    body = 'Для вашей заявки подготовлено предложение. Откройте его в личном кабинете. Наличие проверяется при оформлении.'
    if request.user.locale == 'en':
        body = 'A ticket proposal is ready in your account. Availability will be checked at checkout.'
    notify(request.customer_email, f'Tickethub {request.number}', body, request.id)
    return quote


@transaction.atomic
def withdraw_quote(quote_id, actor, expected_version):
    initial = get_object_or_404(Quote, pk=quote_id)
    request = _lock_request(initial.ticket_request_id, initial.event_id)
    check_version(request, expected_version)
    quote = Quote.objects.select_for_update().get(pk=quote_id)
    require(quote.status in ['DRAFT', 'SENT'], 'INVALID_TRANSITION', 'Предложение уже закрыто.')
    _withdraw_quote_locked(quote)
    if request.status == 'OFFERED' and not request.quotes.filter(status='SENT').exists():
        request.status = 'IN_PROGRESS'
    request.version += 1
    request.save(update_fields=['status', 'version', 'updated_at'])
    return quote


def start_quote_checkout(user, quote_id, expected_total_minor, idempotency_key=None):
    quote = get_object_or_404(Quote, pk=quote_id, ticket_request__user=user)
    return create_hold(user, quote.event_id, {}, expected_total_minor, quote_id=quote.id, idempotency_key=idempotency_key)


def cleanup_expired_quotes():
    now = timezone.now()
    ids = list(Quote.objects.filter(status__in=['SENT', 'DRAFT'], expires_at__lte=now).values_list('id', flat=True))
    count = 0
    for quote_id in ids:
        with transaction.atomic():
            initial = Quote.objects.get(pk=quote_id)
            request = _lock_request(initial.ticket_request_id, initial.event_id)
            quote = Quote.objects.select_for_update().get(pk=quote_id)
            if quote.status not in ['SENT', 'DRAFT'] or quote.expires_at > timezone.now():
                continue
            for hold in CheckoutHold.objects.select_for_update().filter(quote=quote, status='ACTIVE'):
                _release_hold_locked(hold, 'EXPIRED', timezone.now())
            quote.status = 'EXPIRED'
            quote.save(update_fields=['status', 'updated_at'])
            if request.status == 'OFFERED' and not request.quotes.filter(status='SENT', expires_at__gt=timezone.now()).exists():
                request.status = 'IN_PROGRESS'
                request.version += 1
                request.save(update_fields=['status', 'version', 'updated_at'])
            count += 1
    return count
