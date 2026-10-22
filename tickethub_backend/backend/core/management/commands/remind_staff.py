from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from core.email import notify_staff
from orders.models import Order
from orders.services import lock_order, add_history
from payments.selectors import money_summary, sent_summary


class Command(BaseCommand):
    help = 'Не более одного напоминания по заказу в сутки; не меняет деньги или закрепления.'

    def handle(self, *args, **options):
        count = 0
        ids = list(Order.objects.exclude(order_state__in=['CANCELLED', 'REJECTED', 'COMPLETED']).values_list('id', flat=True))
        for order_id in ids:
            with transaction.atomic():
                order = lock_order(order_id)
                now = timezone.now()
                reasons = []
                if order.order_state in ['NEW', 'IN_PROGRESS'] and order.review_due_at < now:
                    reasons.append('review_overdue')
                money = money_summary(order)
                if order.settlement_due_at and order.settlement_due_at < now and money['received_minor'] < order.total_minor:
                    reasons.append('settlement_overdue')
                if order.delivery_due_at and order.delivery_due_at < now and sent_summary(order)['state'] != 'SENT':
                    reasons.append('delivery_overdue')
                if order.items.filter(is_active=True, ticket_unit__stock_basis='EXCLUSIVE_ALLOCATION',
                                      ticket_unit__allocation_until__lte=now).exists():
                    reasons.append('supplier_allocation_expired')
                if not reasons or order.history.filter(event_type='ATTENTION_REMINDER', created_at__date=now.date()).exists():
                    continue
                add_history(order, 'ATTENTION_REMINDER', 'Заказ требует проверки менеджером.', note=', '.join(reasons))
                notify_staff(f'Требует внимания {order.number}: ' + ', '.join(reasons), order.id)
                count += 1
        self.stdout.write(f'Reminders recorded: {count}')
