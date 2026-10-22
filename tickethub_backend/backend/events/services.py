from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from core.errors import require, check_version
from core.email import notify
from .models import Event, Category
from .publication import is_placeholder_category


def public_categories():
    # Traverse in memory, so disabled ancestors also hide their descendants without N+1 queries.
    rows = list(Category.objects.all())
    allowed = {row.pk for row in rows if row.is_active and not is_placeholder_category(row)}
    while True:
        invalid = {row.pk for row in rows if row.pk in allowed and row.parent_id and row.parent_id not in allowed}
        if not invalid:
            break
        allowed.difference_update(invalid)
    return Category.objects.filter(pk__in=allowed)


def public_events():
    return Event.objects.filter(is_published=True, visibility='PUBLIC', category__in=public_categories()).select_related('category', 'venue', 'seating_plan').prefetch_related('participants')


@transaction.atomic
def save_category(instance, data):
    list(Category.objects.select_for_update().order_by('pk').values_list('pk', flat=True))
    data = dict(data)
    expected = data.pop('expected_version', None)
    if instance:
        instance = get_object_or_404(Category.objects.select_for_update(), pk=instance.pk)
        check_version(instance, expected)
    else:
        instance = Category()
    creating = instance._state.adding
    for key, value in data.items():
        setattr(instance, key, value)
    if instance.parent_id:
        instance.parent = Category.objects.get(pk=instance.parent_id)
    instance.full_clean()
    instance.version = 1 if creating else instance.version + 1
    instance.save()
    return instance


def check_orderable(event, now, *, from_quote=False):
    require(settings.PUBLIC_FORMS_ENABLED and settings.ORDER_INTAKE_ENABLED,
            'FORMS_DISABLED', 'Приём новых заказов временно отключён.')
    if settings.REQUIRE_LEGAL_ACCEPTANCE:
        from core.models import ContentPage
        require(ContentPage.objects.filter(slug__in=settings.REQUIRED_LEGAL_SLUGS, is_published=True, approved_by__isnull=False).count() == len(settings.REQUIRED_LEGAL_SLUGS),
                'LEGAL_NOT_READY', 'Документы ещё не опубликованы; новые заказы отключены.', status=503)
    require(from_quote or (not is_placeholder_category(event.category) and event.category.is_active),
            'EVENT_NOT_ORDERABLE', 'Категория мероприятия уточняется; обратитесь к менеджеру.')
    require(from_quote or (event.is_published and event.visibility == 'PUBLIC'),
            'EVENT_NOT_ORDERABLE', 'Событие недоступно для прямого заказа.')
    # This is an order for manual processing, not an online-payment readiness gate.
    # Missing event-specific refund text / translated metadata / a delivery SLA must
    # not hide real available stock. The manager clarifies these before fulfilment.
    from .checkout_policy import intake_time_error
    error = intake_time_error(event, now)
    if error:
        require(False, *error)


@transaction.atomic
def save_event(instance, data, actor):
    data = dict(data)
    expected = data.pop('expected_version', None)
    participants = data.pop('participants', None)
    old = None
    if instance:
        old = get_object_or_404(Event.objects.select_for_update(), pk=instance.pk)
        check_version(old, expected)
        event = old
        previous = (old.status, old.start_at, old.is_published)
    else:
        event = Event()
        previous = None
    # Existing callers (import/stock flows) may already hold the event lock.
    # Preserve event -> category ordering; category updates never lock events.
    list(Category.objects.select_for_update().order_by('pk').values_list('pk', flat=True))
    for key, value in data.items():
        setattr(event, key, value)
    event.category = Category.objects.get(pk=event.category_id)
    event.full_clean()
    event.version = (event.version + 1) if old else 1
    event.save()
    if participants is not None:
        event.participants.set(participants)
    if previous and previous != (event.status, event.start_at, event.is_published):
        from tickets.services import release_event_holds_locked
        from orders.models import OrderHistory
        release_event_holds_locked(event, 'RELEASED')
        for order in event.orders.select_for_update().exclude(order_state__in=['CANCELLED', 'REJECTED']):
            order.version += 1
            if event.delivery_due_at:
                order.delivery_due_at = event.delivery_due_at
            order.save(update_fields=['version', 'delivery_due_at', 'updated_at'])
            OrderHistory.objects.create(order=order, event_type='EVENT_CHANGED', actor=actor,
                                        public_message='Данные мероприятия изменены. Менеджер уточнит дальнейшие действия.')
            text = 'Event details changed. Please check your order or contact our team.' if order.user.locale == 'en' else 'Условия мероприятия изменены. Проверьте заказ или свяжитесь с менеджером.'
            notify(order.customer_email, f'Tickethub — {order.number}', text, order.id)
    return event
