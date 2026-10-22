from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from core.errors import BusinessError, check_version, require
from tickets.models import CheckoutHold
from .calculations import calculate_discount, normalize_code
from .models import PromoCode

MESSAGES = {
    'PROMO_INVALID': 'Промокод не найден или указан неверно.',
    'PROMO_MINIMUM': 'Сумма заказа меньше минимальной суммы для промокода.',
    'PROMO_AMOUNT': 'Этот промокод не подходит для суммы заказа.',
}


def price_promotion(user, hold, code, *, lock=False):
    """Preview or final quote. With lock=True caller must be in an atomic block.

    Lock order for checkout: User -> Event -> Hold -> TicketUnits -> PromoCode.
    Promo edits lock any referenced Event rows before the PromoCode row too.
    """
    require(not hold.quote_id, 'PROMO_QUOTE', 'Промокод не суммируется с персональным предложением.')
    try:
        normalized = normalize_code(code)
    except ValueError:
        raise BusinessError('PROMO_INVALID', MESSAGES['PROMO_INVALID'], status=400)
    queryset = PromoCode.objects.select_for_update() if lock else PromoCode.objects.all()
    promo = queryset.filter(code=normalized).first()
    require(promo is not None and promo.is_active, 'PROMO_INVALID', MESSAGES['PROMO_INVALID'], status=400)
    now = timezone.now()  # after any wait for the promo row lock
    require(hold.status == 'ACTIVE' and hold.expires_at > now, 'HOLD_EXPIRED', 'Время оформления истекло.')
    require(promo.starts_at is None or promo.starts_at <= now, 'PROMO_NOT_STARTED', 'Промокод ещё не действует.', status=400)
    require(promo.ends_at is None or now < promo.ends_at, 'PROMO_EXPIRED', 'Срок действия промокода закончился.', status=400)
    require(promo.event_id is None or promo.event_id == hold.event_id, 'PROMO_EVENT', 'Промокод действует для другого мероприятия.', status=400)
    if promo.usage_limit is not None:
        require(promo.redemptions.count() < promo.usage_limit, 'PROMO_LIMIT', 'Лимит применений промокода исчерпан.', status=400)
    if promo.per_user_limit is not None:
        require(promo.redemptions.filter(user=user).count() < promo.per_user_limit,
                'PROMO_USER_LIMIT', 'Вы уже использовали этот промокод допустимое количество раз.', status=400)
    try:
        discount = calculate_discount(hold.total_minor, promo.kind, promo.value,
                    minimum=promo.minimum_total_minor, maximum=promo.maximum_discount_minor)
    except ValueError as exc:
        code = str(exc)
        raise BusinessError(code, MESSAGES.get(code, 'Не удалось рассчитать скидку.'), status=400,
                            details={'minimum_total_minor': promo.minimum_total_minor})
    return promo, {'code': promo.code, 'promo_version': promo.version,
                   'subtotal_minor': hold.total_minor, 'discount_minor': discount,
                   'total_minor': hold.total_minor - discount, 'currency': 'RUB', 'hold_id': hold.id}


def preview_promotion(user, hold_id, code):
    # Ownership is checked even if the caller knows another customer's hold UUID.
    hold = get_object_or_404(CheckoutHold, pk=hold_id, user=user)
    require(hold.status == 'ACTIVE' and hold.expires_at > timezone.now(), 'HOLD_EXPIRED', 'Время оформления истекло.')
    _, result = price_promotion(user, hold, code)
    return result


@transaction.atomic
def save_promotion(instance, data):
    data = dict(data)
    expected = data.pop('expected_version', None)
    # Lock referenced events before the promo row, including scope changes. This
    # also avoids a reversed lock order from PostgreSQL foreign-key checks.
    from events.models import Event
    event_ids = set()
    if instance and instance.event_id:
        event_ids.add(instance.event_id)
    if data.get('event'):
        event_ids.add(data['event'].pk)
    list(Event.objects.select_for_update().filter(pk__in=event_ids).order_by('pk'))
    if instance:
        obj = get_object_or_404(PromoCode.objects.select_for_update(), pk=instance.pk)
        check_version(obj, expected)
    else:
        obj = PromoCode()
    for key, value in data.items():
        setattr(obj, key, value)
    obj.full_clean()
    if instance:
        obj.version += 1
    obj.save()
    return obj
