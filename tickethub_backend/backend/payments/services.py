from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from core.errors import require, check_version
from core.validation import fingerprint
from orders.models import CustomerCase
from orders.services import lock_order, touch_order, add_history, sync_sold_units, _repeat
from tickets.models import TicketUnit
from .models import FinancialEntry
from .selectors import money_summary, sent_item_ids


def _case_refunded(case):
    return sum(entry.amount_minor if entry.direction == 'NORMAL' else -entry.amount_minor
               for entry in case.financial_entries.all())


def _refresh_paid_date(order):
    rows = list(order.financial_entries.filter(kind='PAYMENT'))
    reversed_ids = {entry.reversal_of_id for entry in rows if entry.direction == 'REVERSAL'}
    received = 0
    first_paid = None
    for entry in rows:
        if entry.direction != 'NORMAL' or entry.id in reversed_ids:
            continue
        received += entry.amount_minor
        if received >= order.total_minor:
            first_paid = entry.occurred_at
            break
    order.first_paid_at = first_paid


def _finish_money_operation(order, actor, message):
    _refresh_paid_date(order)
    touch_order(order)
    sync_sold_units(order)
    add_history(order, 'FINANCIAL_ENTRY', message, actor)
    money = money_summary(order)
    if money['received_minor'] == order.total_minor:
        from analytics.services import record_order_event
        record_order_event(order, 'PAYMENT_RECEIVED')


@transaction.atomic
def record_payment(order_id, actor, data, idempotency_key):
    order = lock_order(order_id)
    digest = fingerprint(data)
    existing = _repeat(order.financial_entries.filter(idempotency_key=idempotency_key).first(), digest)
    if existing:
        return existing, False
    check_version(order, data['expected_version'])
    kind, amount = data['kind'], data['amount_minor']
    require(kind in ['PAYMENT', 'DIRECT_EXPENSE', 'SUPPLIER_REFUND'], 'INVALID_KIND', 'Возврат проводится через одобренное обращение.', status=400)
    require(amount > 0, 'INVALID_AMOUNT', 'Сумма должна быть положительной.', status=400)
    require(order.created_at <= data['occurred_at'] <= timezone.now(), 'INVALID_TIME', 'Укажите фактическое время операции.', status=400)
    money = money_summary(order)
    if kind == 'PAYMENT':
        require(order.order_state not in ['CANCELLED', 'REJECTED'], 'ORDER_CLOSED', 'Нельзя фиксировать новую оплату закрытого заказа.')
        require(money['received_minor'] + amount <= order.total_minor, 'OVERPAYMENT', 'Сумма превышает стоимость заказа.')
    entry = FinancialEntry.objects.create(order=order, kind=kind, amount_minor=amount,
                                           occurred_at=data['occurred_at'], method=data['method'], reference=data['reference'],
                                           notes=data.get('notes', ''), created_by=actor,
                                           idempotency_key=idempotency_key, request_hash=digest)
    _finish_money_operation(order, actor, 'Обновлена информация о расчётах по заказу.')
    return entry, True


@transaction.atomic
def decide_case(case_id, actor, expected_version, decision, public_response, *, amount_minor=None, internal_notes=''):
    initial = get_object_or_404(CustomerCase, pk=case_id)
    order = lock_order(initial.order_id)
    case = CustomerCase.objects.select_for_update().get(pk=case_id)
    check_version(case, expected_version)
    require(case.status in ['NEW', 'IN_PROGRESS', 'NEED_INFO'], 'INVALID_TRANSITION', 'Решение уже принято.')
    require(decision in ['APPROVED', 'REJECTED', 'IN_PROGRESS', 'NEED_INFO', 'CLOSED'], 'INVALID_TRANSITION', 'Неизвестное решение.', status=400)
    require(public_response.strip(), 'RESPONSE_REQUIRED', 'Нужен ответ клиенту.', status=400)
    if decision == 'APPROVED':
        require(case.kind == 'REFUND_REQUEST', 'INVALID_KIND', 'Одобрение суммы применяется к запросу возврата.', status=400)
        require(amount_minor is not None and amount_minor > 0, 'INVALID_AMOUNT', 'Укажите положительную сумму возврата.', status=400)
        money = money_summary(order)
        outstanding = sum(other.approved_minor - _case_refunded(other)
                          for other in order.cases.filter(status='APPROVED').exclude(pk=case.id))
        require(amount_minor <= money['net_received_minor'] - outstanding,
                'REFUND_LIMIT', 'Сумма превышает полученные деньги с учётом других решений.')
        items = list(case.items.all())
        require(bool(items) and amount_minor <= sum(i.sale_price_minor for i in items),
                'REFUND_LIMIT', 'Сумма превышает стоимость выбранных билетов.')
        require(not order.cases.filter(items__in=items, status='APPROVED').exclude(pk=case.id).exists(),
                'REFUND_EXISTS', 'По одной из позиций уже есть одобренный возврат.')
        require(not order.cases.filter(items__in=items, kind='REFUND_REQUEST', status='CLOSED', approved_minor__isnull=False)
                .exclude(pk=case.id).exists(), 'REFUND_EXISTS', 'Одна из позиций уже возвращена.')
        case.approved_minor = amount_minor
    case.status = decision
    case.public_response = public_response
    case.internal_notes = internal_notes
    if decision in ['APPROVED', 'REJECTED', 'CLOSED']:
        case.decided_by, case.decided_at = actor, timezone.now()
    case.version += 1
    case.save()
    touch_order(order)
    add_history(order, 'CASE_DECISION', 'Обновлён ответ по обращению.', actor, internal_notes)
    return case


def approve_refund(case_id, actor, expected_version, amount_minor, public_response, internal_notes=''):
    return decide_case(case_id, actor, expected_version, 'APPROVED', public_response,
                       amount_minor=amount_minor, internal_notes=internal_notes)


@transaction.atomic
def record_refund(case_id, actor, data, idempotency_key):
    initial = get_object_or_404(CustomerCase, pk=case_id)
    order = lock_order(initial.order_id)
    digest = fingerprint({'case_id': str(case_id), **data})
    existing = _repeat(order.financial_entries.filter(idempotency_key=idempotency_key).first(), digest)
    if existing:
        return existing, False
    check_version(order, data['expected_version'])
    case = CustomerCase.objects.select_for_update().get(pk=case_id)
    require(case.status == 'APPROVED' and case.approved_minor is not None, 'REFUND_NOT_APPROVED', 'Возврат не одобрен.')
    amount = data['amount_minor']
    require(amount > 0 and amount <= case.approved_minor - _case_refunded(case), 'REFUND_LIMIT', 'Сумма превышает остаток решения.')
    require(amount <= money_summary(order)['net_received_minor'], 'REFUND_LIMIT', 'Нельзя вернуть больше полученного.')
    require(case.decided_at <= data['occurred_at'] <= timezone.now(), 'INVALID_TIME', 'Укажите время после одобрения возврата.', status=400)
    entry = FinancialEntry.objects.create(order=order, kind='CUSTOMER_REFUND', amount_minor=amount, refund_case=case,
                                           occurred_at=data['occurred_at'], method=data['method'], reference=data['reference'],
                                           notes=data.get('notes', ''), created_by=actor,
                                           idempotency_key=idempotency_key, request_hash=digest)
    settled = _case_refunded(case) == case.approved_minor
    for item in case.items.order_by('ticket_unit_id'):
        unit = TicketUnit.objects.select_for_update().get(pk=item.ticket_unit_id)
        # A refunded/sent ticket needs explicit staff validation before resale.
        # Never disturb a later order if a previously cancelled ticket was resold.
        if item.is_active or not unit.order_items.filter(is_active=True).exists():
            unit.status = 'BLOCKED'
            unit.current_hold = None
            unit.version += 1
            unit.save(update_fields=['status', 'current_hold', 'version', 'updated_at'])
        if settled and item.is_active:
            item.is_active = False
            item.save(update_fields=['is_active', 'updated_at'])
    if settled:
        case.status = 'CLOSED'
    case.version += 1
    case.save(update_fields=['status', 'version', 'updated_at'])
    if not order.items.filter(is_active=True).exists():
        order.order_state = 'CANCELLED'
    elif order.order_state == 'COMPLETED':
        order.order_state = 'CONFIRMED'
    _finish_money_operation(order, actor, 'Зафиксирован фактический возврат денег.')
    return entry, True


@transaction.atomic
def reverse_entry(entry_id, actor, data, idempotency_key):
    original = get_object_or_404(FinancialEntry, pk=entry_id)
    order = lock_order(original.order_id)
    digest = fingerprint({'reverse_entry_id': str(entry_id), **data})
    existing = _repeat(order.financial_entries.filter(idempotency_key=idempotency_key).first(), digest)
    if existing:
        return existing, False
    check_version(order, data['expected_version'])
    original = FinancialEntry.objects.select_for_update().get(pk=entry_id)
    require(original.direction == 'NORMAL' and not FinancialEntry.objects.filter(reversal_of=original).exists(),
            'ALREADY_REVERSED', 'Запись уже сторнирована либо сама является сторно.')
    require(bool(data['reason'].strip()), 'REASON_REQUIRED', 'Укажите причину.', status=400)
    require(original.occurred_at <= data['occurred_at'] <= timezone.now(), 'INVALID_TIME', 'Укажите фактическое время корректировки.', status=400)
    money = money_summary(order)
    if original.kind == 'PAYMENT':
        require(money['received_minor'] - original.amount_minor >= money['refunded_minor'],
                'REFUND_LIMIT', 'Сначала исправьте зависимые возвраты.')
        require(not sent_item_ids(order), 'DELIVERY_EXISTS', 'Сначала проверьте и при ошибке аннулируйте отправку.')
        pending = sum(case.approved_minor - _case_refunded(case) for case in order.cases.filter(status='APPROVED'))
        require(money['net_received_minor'] - original.amount_minor >= pending,
                'OPEN_REFUND', 'Корректировка нарушит уже одобренные возвраты.')
    entry = FinancialEntry.objects.create(order=order, kind=original.kind, amount_minor=original.amount_minor,
                                           direction='REVERSAL', reversal_of=original, refund_case=original.refund_case,
                                           occurred_at=data['occurred_at'], method=original.method, reference=original.reference,
                                           notes=data['reason'], created_by=actor,
                                           idempotency_key=idempotency_key, request_hash=digest)
    if original.refund_case_id:
        case = original.refund_case
        case.status = 'APPROVED'
        case.version += 1
        case.save(update_fields=['status', 'version', 'updated_at'])
    if order.order_state == 'COMPLETED':
        order.order_state = 'CONFIRMED'
    _finish_money_operation(order, actor, 'Исправлена финансовая запись.')
    return entry, True
