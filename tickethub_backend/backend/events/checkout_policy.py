"""Time rules for a manually processed order; no online-payment readiness flags."""
from datetime import timedelta


def intake_time_error(event, now):
    if event.status in {'CANCELLED', 'FINISHED'}:
        return 'EVENT_CLOSED', 'Мероприятие отменено или завершено.'
    if event.start_at is not None and not event.date_tba and event.start_at <= now:
        return 'EVENT_STARTED', 'Оформление на начавшееся мероприятие закрыто.'
    if event.sale_deadline is not None and event.sale_deadline <= now:
        return 'SALES_CLOSED', 'Срок приёма заказов на мероприятие закончился.'
    return None


def hold_deadline(event, now, seconds):
    values = [now + timedelta(seconds=seconds)]
    if event.sale_deadline and event.sale_deadline > now:
        values.append(event.sale_deadline)
    if event.start_at and not event.date_tba and event.start_at > now:
        values.append(event.start_at)
    return min(values)


def order_deadlines(event, now):
    review = [now + timedelta(hours=24)]
    if event.sale_deadline and event.sale_deadline > now:
        review.append(event.sale_deadline)
    if event.start_at and not event.date_tba and event.start_at > now:
        review.append(event.start_at)
    delivery = event.delivery_due_at
    if delivery is not None and delivery <= now:
        delivery = None
    return min(review), delivery
