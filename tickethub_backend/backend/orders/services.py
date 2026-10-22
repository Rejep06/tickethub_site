from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from core.consents import accept_documents
from core.email import notify, notify_staff
from core.errors import require, check_version
from core.validation import fingerprint, validate_phone
from events.models import Event
from events.services import check_orderable
from tickets.models import CheckoutHold, TicketUnit
from tickets.services import valid_stock
from users.models import User
from payments.selectors import money_summary, sent_summary, sent_item_ids
from .models import Order, OrderItem, OrderHistory, CustomerCase, DeliveryRecord


def require_customer_profile(user):
    require(user.is_active and user.email_verified_at and user.name.strip() and user.phone,
            'PROFILE_INCOMPLETE', 'Нужны имя, телефон и подтверждённый email.', status=400)
    validate_phone(user.phone)


def add_history(order, kind, message, actor=None, note=''):
    return OrderHistory.objects.create(order=order, event_type=kind, public_message=message,
                                       actor=actor, internal_note=note)


def touch_order(order):
    order.version += 1
    order.save()


def lock_order(order_id):
    """Called inside atomic: Event first, then Order. All stock writers agree."""
    initial = get_object_or_404(Order.objects.only('event_id'), pk=order_id)
    Event.objects.select_for_update().get(pk=initial.event_id)
    return Order.objects.select_for_update().get(pk=order_id)


def _repeat(existing, request_hash):
    if existing:
        require(existing.request_hash == request_hash, 'IDEMPOTENCY_CONFLICT',
                'Этот ключ уже использован для другого запроса.')
    return existing


@transaction.atomic
def create_order_from_hold(user, data, idempotency_key, analytics_session_key=''):
    user = User.objects.select_for_update().get(pk=user.pk)
    digest = fingerprint(data)
    existing = _repeat(Order.objects.filter(user=user, idempotency_key=idempotency_key).first(), digest)
    if existing:
        return existing, False
    initial = get_object_or_404(CheckoutHold, pk=data['hold_id'], user=user)
    event = Event.objects.select_for_update().get(pk=initial.event_id)
    hold = CheckoutHold.objects.select_for_update().get(pk=initial.pk)
    now = timezone.now()
    require(hold.status == 'ACTIVE' and hold.expires_at > now, 'HOLD_EXPIRED', 'Резерв недействителен.')
    require(not Order.objects.filter(hold=hold).exists(), 'HOLD_CONVERTED', 'Резерв уже стал заказом.')
    require(not Order.objects.filter(user=user, event=event, order_state__in=['NEW', 'IN_PROGRESS']).exists(),
            'ORDER_EXISTS', 'Заказ по этому событию уже ожидает обработки.')
    check_orderable(event, now, from_quote=bool(hold.quote_id))
    require(event.version == hold.event_version, 'EVENT_CHANGED', 'Условия события изменились. Повторите оформление.')
    require_customer_profile(user)
    fan_answer = data.get('fan_id_answer', '')
    require(not event.fan_id_required or fan_answer in ['HAS_FAN_ID', 'NEEDS_HELP', 'NOT_SURE'],
            'FAN_ID_ACK_REQUIRED', 'Укажите, нужна ли помощь с картой болельщика.', status=400)
    documents = accept_documents(user, data.get('accepted_documents', {}), 'ORDER')
    quote = None
    if hold.quote_id:
        from ticket_requests.models import Quote
        quote = Quote.objects.select_for_update().get(pk=hold.quote_id)
        require(quote.status == 'SENT' and quote.expires_at > now and quote.ticket_request.user_id == user.id,
                'QUOTE_UNAVAILABLE', 'Предложение недоступно.')
        require(quote.ticket_request.status in ['OFFERED', 'IN_PROGRESS'], 'QUOTE_UNAVAILABLE', 'Заявка закрыта.')
    hold_items = list(hold.items.select_related('ticket_unit').order_by('ticket_unit_id'))
    require(bool(hold_items), 'EMPTY_ORDER', 'В резерве нет билетов.')
    units = {unit.id: unit for unit in TicketUnit.objects.select_for_update().filter(
        pk__in=[item.ticket_unit_id for item in hold_items]).order_by('id')}
    require(all(unit.status == 'CHECKOUT_HELD' and unit.current_hold_id == hold.id and valid_stock(unit, now)
                for unit in units.values()) and len(units) == len(hold_items),
            'SEAT_UNAVAILABLE', 'Один из билетов больше недоступен.')
    require(sum(item.sale_price_minor for item in hold_items) == hold.total_minor, 'INVALID_TOTAL', 'Некорректная сумма резерва.')
    from promotions.services import price_promotion
    from promotions.calculations import allocate_discount
    from promotions.models import PromoRedemption
    promo = None
    pricing = {'subtotal_minor': hold.total_minor, 'discount_minor': 0, 'total_minor': hold.total_minor}
    if data.get('promo_code'):
        promo, pricing = price_promotion(user, hold, data['promo_code'], lock=True)
        require(data.get('expected_total_minor') == pricing['total_minor']
                and data.get('expected_discount_minor') == pricing['discount_minor']
                and data.get('expected_promo_version') == pricing['promo_version'],
                'PROMO_CHANGED', 'Условия промокода изменились. Примените его ещё раз и проверьте сумму.',
                details={key: pricing[key] for key in ['total_minor', 'discount_minor', 'promo_version']})
    else:
        require(data.get('expected_discount_minor', 0) == 0 and not data.get('expected_promo_version'),
                'PROMO_INVALID', 'Скидка требует действующего промокода.', status=400)
        require(data.get('expected_total_minor', hold.total_minor) == hold.total_minor,
                'PRICE_CHANGED', 'Проверьте итоговую сумму заказа.')
    # A promo lock can have waited behind another customer's transaction.
    now = timezone.now()
    require(hold.expires_at > now, 'HOLD_EXPIRED', 'Время оформления истекло.')
    check_orderable(event, now, from_quote=bool(hold.quote_id))
    try:
        discounts = allocate_discount([item.sale_price_minor for item in hold_items], pricing['discount_minor'])
    except ValueError:
        require(False, 'INVALID_TOTAL', 'Суммы билетов не подходят для оформления. Обратитесь к менеджеру.', status=400)
    from events.checkout_policy import order_deadlines
    review_due, delivery_due = order_deadlines(event, now)
    order = Order.objects.create(
        user=user, event=event, hold=hold, quote=quote,
        ticket_request=quote.ticket_request if quote else None,
        origin='SITE_REQUEST' if quote else 'SITE_DIRECT',
        customer_name=user.name, customer_email=user.email, customer_phone=user.phone,
        customer_comment=data.get('comment', ''), fan_id_answer=fan_answer if event.fan_id_required else '',
        fan_id_help_state='REQUESTED' if event.fan_id_required and fan_answer != 'HAS_FAN_ID' else 'NOT_NEEDED',
        subtotal_minor=pricing['subtotal_minor'], discount_minor=pricing['discount_minor'],
        promo_code=promo.code if promo else '', total_minor=pricing['total_minor'],
        review_due_at=review_due, delivery_due_at=delivery_due,
        event_snapshot={'title_ru': event.title_ru, 'title_en': event.title_en,
                        'start_at': event.start_at.isoformat() if event.start_at and not event.date_tba else None, 'timezone': event.venue.timezone,
                        'venue_ru': event.venue.name_ru, 'venue_en': event.venue.name_en,
                        'fan_id_required': event.fan_id_required,
                        'fan_id_description_ru': event.fan_id_description_ru,
                        'fan_id_description_en': event.fan_id_description_en,
                        'refund_policy_ru': event.refund_policy_ru, 'refund_policy_en': event.refund_policy_en,
                        'delivery_due_at': delivery_due.isoformat() if delivery_due else None,
                        'together_confirmed': bool(quote and quote.together_confirmed)},
        accepted_document_versions=documents, idempotency_key=idempotency_key, request_hash=digest,
        analytics_session_key=analytics_session_key)
    for item, discount in zip(hold_items, discounts):
        unit = units[item.ticket_unit_id]
        OrderItem.objects.create(order=order, ticket_unit=unit, name_ru=item.name_ru, name_en=item.name_en,
                                 sector=item.sector, row=item.row, seat_number=item.seat_number,
                                 original_price_minor=item.sale_price_minor, discount_minor=discount,
                                 sale_price_minor=item.sale_price_minor - discount, purchase_price_minor=unit.purchase_price_minor)
        # Checkout timeout no longer owns this ticket after order submission.
        unit.status, unit.current_hold = 'ORDER_HELD', None
        unit.version += 1
        unit.save(update_fields=['status', 'current_hold', 'version', 'updated_at'])
    if promo:
        PromoRedemption.objects.create(promo=promo, order=order, user=user, code=promo.code,
                                       discount_minor=pricing['discount_minor'], promo_version=promo.version)
    hold.status = 'CONVERTED'
    hold.save(update_fields=['status', 'updated_at'])
    if quote:
        quote.status = 'ACCEPTED'
        quote.save(update_fields=['status', 'updated_at'])
        request = quote.ticket_request
        request.status = 'CONVERTED'
        request.version += 1
        request.save(update_fields=['status', 'version', 'updated_at'])
    add_history(order, 'ORDER_CREATED', 'Заказ получен.', user)
    from analytics.services import record_order_event
    record_order_event(order, 'ORDER_CREATED')
    body = f'Заказ {order.number} получен. Менеджер свяжется с вами. Онлайн-оплаты на сайте нет.'
    if user.locale == 'en':
        body = f'Order {order.number} received. A manager will contact you. No online payment is required on this site.'
    notify(order.customer_email, f'Tickethub {order.number}', body, order.id)
    total_text = f'{order.total_minor // 100:,}'.replace(',', ' ') + f'.{order.total_minor % 100:02d} ₽'
    promo_text = f'\nПромокод: {order.promo_code}; скидка {order.discount_minor // 100}.{order.discount_minor % 100:02d} ₽' if order.promo_code else ''
    notify_staff(f'Новый заказ {order.number}', order.id,
                 path=f'/ru/staff/orders/{order.id}',
                 body=f'{event.title_ru}\nБилетов: {len(hold_items)}\nК оплате: {total_text}{promo_text}')
    return order, True


@transaction.atomic
def start_processing_order(order_id, actor, expected_version):
    order = lock_order(order_id)
    check_version(order, expected_version)
    require(order.order_state == 'NEW', 'INVALID_TRANSITION', 'В работу можно взять только новый заказ.')
    order.order_state = 'IN_PROGRESS'
    order.manager = order.manager or actor
    touch_order(order)
    add_history(order, 'ORDER_PROCESSING_STARTED', 'Менеджер обрабатывает заказ.', actor)
    from analytics.services import record_order_event
    record_order_event(order, 'ORDER_PROCESSING_STARTED')
    return order


@transaction.atomic
def update_order_operations(order_id, actor, data):
    order = lock_order(order_id)
    check_version(order, data.pop('expected_version'))
    if 'manager_id' in data:
        manager = get_object_or_404(User, pk=data.pop('manager_id'), is_active=True, is_staff=True, staff_role__in=['MANAGER', 'ADMIN'])
        order.manager = manager
    for field, value in data.items():
        setattr(order, field, value)
    if order.delivery_due_at and order.event.start_at and not order.event.date_tba:
        require(order.delivery_due_at < order.event.start_at, 'INVALID_DEADLINE', 'Срок выдачи должен быть до события.', status=400)
    touch_order(order)
    add_history(order, 'OPERATIONS_UPDATED', 'Обновлена информация по обработке заказа.', actor)
    return order


@transaction.atomic
def record_contact(order_id, actor, expected_version, note=''):
    order = lock_order(order_id)
    check_version(order, expected_version)
    require(order.order_state in ['NEW', 'IN_PROGRESS', 'CONFIRMED'], 'INVALID_TRANSITION', 'Заказ закрыт.')
    order.first_contact_at = order.first_contact_at or timezone.now()
    touch_order(order)
    add_history(order, 'CONTACT_RECORDED', 'Менеджер связался с клиентом.', actor, note)
    return order


def sync_sold_units(order):
    money = money_summary(order)
    target = 'SOLD' if order.order_state in ['CONFIRMED', 'COMPLETED'] and money['received_minor'] == order.total_minor else 'ORDER_HELD'
    for item in order.items.filter(is_active=True).order_by('ticket_unit_id'):
        unit = TicketUnit.objects.select_for_update().get(pk=item.ticket_unit_id)
        if unit.status in ['SOLD', 'ORDER_HELD']:
            unit.status = target
            unit.version += 1
            unit.save(update_fields=['status', 'version', 'updated_at'])


@transaction.atomic
def confirm_order(order_id, actor, expected_version):
    order = lock_order(order_id)
    check_version(order, expected_version)
    require(order.order_state == 'IN_PROGRESS', 'INVALID_TRANSITION', 'Сначала возьмите заказ в работу.')
    require(order.event.status not in ['CANCELLED', 'FINISHED']
            and (order.event.start_at is None or order.event.date_tba or order.event.start_at > timezone.now()),
            'EVENT_NOT_ORDERABLE', 'Проверьте состояние события.')
    require(order.items.filter(is_active=True).exists(), 'EMPTY_ORDER', 'В заказе нет активных билетов.')
    require(not order.items.filter(is_active=True, ticket_unit__status='BLOCKED').exists(), 'UNIT_BLOCKED', 'Нужно проверить заблокированные билеты.')
    require(all(valid_stock(item.ticket_unit, timezone.now()) for item in order.items.filter(is_active=True).select_related('ticket_unit')),
            'STOCK_NOT_CONFIRMED', 'Закрепление поставщика истекло; сначала уточните наличие.')
    order.order_state = 'CONFIRMED'
    order.confirmed_at = timezone.now()
    touch_order(order)
    sync_sold_units(order)
    add_history(order, 'ORDER_CONFIRMED', 'Заказ подтверждён.', actor)
    from analytics.services import record_order_event
    record_order_event(order, 'ORDER_CONFIRMED')
    notify(order.customer_email, f'Tickethub {order.number}',
           'Заказ подтверждён.' if order.user.locale == 'ru' else 'Your order has been confirmed.', order.id)
    return order


@transaction.atomic
def cancel_order(order_id, actor, expected_version, reason, no_pending_settlements=False, *, reject=False):
    order = lock_order(order_id)
    check_version(order, expected_version)
    require(order.order_state not in ['CANCELLED', 'REJECTED'], 'INVALID_TRANSITION', 'Заказ уже закрыт.')
    require(bool(reason.strip()), 'REASON_REQUIRED', 'Укажите причину.', status=400)
    money = money_summary(order)
    ever_sent = sent_item_ids(order, include_voided=True)
    if reject:
        require(order.order_state in ['NEW', 'IN_PROGRESS'] and money['received_minor'] == 0 and not ever_sent,
                'INVALID_TRANSITION', 'Отклонение возможно только до оплаты и выдачи.')
    safe = money['received_minor'] == 0 and not ever_sent
    if safe:
        require(no_pending_settlements, 'SETTLEMENT_CONFIRMATION_REQUIRED', 'Подтвердите отсутствие незавершённых расчётов.')
    for item in order.items.filter(is_active=True).order_by('ticket_unit_id'):
        unit = TicketUnit.objects.select_for_update().get(pk=item.ticket_unit_id)
        unit.status = 'AVAILABLE' if safe and valid_stock(unit, timezone.now() + timedelta(seconds=settings.HOLD_SECONDS)) else 'BLOCKED'
        unit.current_hold = None
        unit.version += 1
        unit.save(update_fields=['status', 'current_hold', 'version', 'updated_at'])
        item.is_active = False
        item.save(update_fields=['is_active', 'updated_at'])
    order.order_state = 'REJECTED' if reject else 'CANCELLED'
    touch_order(order)
    add_history(order, order.order_state, 'Заказ отклонён.' if reject else 'Заказ отменён. Расчёты при необходимости уточняет менеджер.', actor, reason)
    return order


def reject_order(order_id, actor, expected_version, reason, no_pending_settlements=False):
    return cancel_order(order_id, actor, expected_version, reason, no_pending_settlements, reject=True)


@transaction.atomic
def complete_order(order_id, actor, expected_version):
    order = lock_order(order_id)
    check_version(order, expected_version)
    require(order.order_state == 'CONFIRMED', 'INVALID_TRANSITION', 'Нужен подтверждённый заказ.')
    active = list(order.items.filter(is_active=True))
    money = money_summary(order)
    require(bool(active), 'EMPTY_ORDER', 'Пустой заказ не является выполненным.')
    require(money['net_received_minor'] >= sum(i.sale_price_minor for i in active), 'PAYMENT_REQUIRED', 'Остались незавершённые расчёты.')
    require(sent_summary(order)['state'] == 'SENT', 'DELIVERY_REQUIRED', 'Отправлены не все билеты.')
    require(not order.cases.exclude(status__in=['REJECTED', 'CLOSED']).exists(), 'OPEN_CASE', 'Сначала завершите обращения.')
    order.order_state = 'COMPLETED'
    touch_order(order)
    add_history(order, 'ORDER_COMPLETED', 'Заказ выполнен.', actor)
    from analytics.services import record_order_event
    record_order_event(order, 'ORDER_COMPLETED')
    return order


@transaction.atomic
def create_refund_request(user, order_id, data):
    initial = get_object_or_404(Order, pk=order_id, user=user)
    order = lock_order(initial.pk)
    ids = set(data.get('item_ids') or list(order.items.values_list('id', flat=True)))
    require(bool(ids) and order.items.filter(pk__in=ids).count() == len(ids), 'INVALID_ITEMS', 'Проверьте позиции заказа.', status=400)
    kind = data.get('kind', 'REFUND_REQUEST')
    for case in order.cases.filter(kind=kind).exclude(status__in=['REJECTED', 'CLOSED']):
        if set(case.items.values_list('id', flat=True)) == ids:
            return case, False
    case = CustomerCase.objects.create(order=order, user=user, kind=kind, reason=data['reason'], requested_minor=data.get('requested_minor'))
    case.items.set(order.items.filter(pk__in=ids))
    add_history(order, 'CASE_CREATED', 'Обращение передано менеджеру.', user)
    touch_order(order)
    notify_staff(f'Обращение по заказу {order.number}', order.id)
    return case, True


@transaction.atomic
def record_delivery(order_id, actor, data, idempotency_key):
    order = lock_order(order_id)
    digest = fingerprint(data)
    existing = _repeat(order.deliveries.filter(idempotency_key=idempotency_key).first(), digest)
    if existing:
        return existing, False
    check_version(order, data['expected_version'])
    require(order.order_state in ['CONFIRMED', 'COMPLETED'], 'INVALID_TRANSITION', 'Сначала подтвердите заказ.')
    money = money_summary(order)
    require(money['received_minor'] == order.total_minor, 'PAYMENT_REQUIRED', 'Сначала зафиксируйте полную оплату.')
    ids = set(data['item_ids'])
    items = list(order.items.filter(pk__in=ids, is_active=True))
    require(len(items) == len(ids) and bool(ids), 'INVALID_ITEMS', 'Проверьте активные позиции заказа.', status=400)
    require(not order.cases.filter(items__in=items, status='APPROVED').exists(), 'OPEN_REFUND', 'По этим билетам одобрен возврат.')
    require(not any(i.ticket_unit.status == 'BLOCKED' for i in items), 'UNIT_BLOCKED', 'Билет заблокирован.')
    allowed_emails = {order.customer_email.lower()}
    if order.user.email_verified_at:
        allowed_emails.add(order.user.email.lower())
    require(data['recipient_email'].lower() in allowed_emails, 'EMAIL_MISMATCH',
            'Используйте email заказа либо текущий подтверждённый email покупателя.', status=400)
    require(order.created_at <= data['sent_at'] <= timezone.now(), 'INVALID_TIME', 'Укажите фактическое время отправки.', status=400)
    record = DeliveryRecord.objects.create(order=order, sent_by=actor, recipient_email=data['recipient_email'],
                                            sent_at=data['sent_at'], note=data.get('note', ''), message_id=data.get('message_id', ''),
                                            idempotency_key=idempotency_key, request_hash=digest)
    record.items.set(items)
    touch_order(order)
    add_history(order, 'DELIVERY_RECORDED', f'Отмечена отправка: {len(items)} билетов.', actor)
    if sent_summary(order)['state'] == 'SENT':
        from analytics.services import record_order_event
        record_order_event(order, 'TICKET_SENT')
    return record, True


@transaction.atomic
def void_delivery(delivery_id, actor, expected_version, reason):
    original = get_object_or_404(DeliveryRecord, pk=delivery_id)
    order = lock_order(original.order_id)
    check_version(order, expected_version)
    record = DeliveryRecord.objects.select_for_update().get(pk=delivery_id)
    require(record.status == 'SENT' and bool(reason.strip()), 'INVALID_TRANSITION', 'Нужны действующая запись и причина.')
    record.status, record.void_reason, record.voided_at = 'VOIDED', reason, timezone.now()
    record.save(update_fields=['status', 'void_reason', 'voided_at', 'updated_at'])
    if order.order_state == 'COMPLETED':
        order.order_state = 'CONFIRMED'
    touch_order(order)
    add_history(order, 'DELIVERY_VOIDED', 'Исправлена ошибочная отметка отправки.', actor, reason)
    return record


@transaction.atomic
def update_item_cost(item_id, actor, expected_version, purchase_price_minor, reason, zero_confirmed=False):
    initial = get_object_or_404(OrderItem.objects.only('order_id'), pk=item_id)
    order = lock_order(initial.order_id)
    check_version(order, expected_version)
    require(reason.strip(), 'REASON_REQUIRED', 'Укажите основание исправления себестоимости.', status=400)
    require(purchase_price_minor >= 0 and (purchase_price_minor != 0 or zero_confirmed),
            'INVALID_COST', 'Нулевая себестоимость требует отдельного подтверждения.', status=400)
    item = OrderItem.objects.select_for_update().get(pk=item_id)
    previous = item.purchase_price_minor
    item.purchase_price_minor = purchase_price_minor
    item.save(update_fields=['purchase_price_minor', 'updated_at'])
    touch_order(order)
    add_history(order, 'COST_UPDATED', '', actor,
                f'Item {item.id}: {previous} -> {purchase_price_minor} kopecks. {reason}')
    return order
