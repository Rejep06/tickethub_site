"""Read-only diagnostics for manual-order intake; never enables a setting silently."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from core.errors import BusinessError
from core.public_api import public_configuration
from events.models import Event
from events.services import check_orderable
from tickets.services import available_units


class Command(BaseCommand):
    help = 'Показывает, что мешает заказу попасть в очередь менеджера. Ничего не меняет.'

    def add_arguments(self, parser):
        parser.add_argument('--event', help='Slug мероприятия')

    def handle(self, *args, **options):
        cfg = public_configuration()
        for key in ['public_forms_enabled', 'order_intake_enabled', 'legal_ready', 'online_payments_enabled']:
            self.stdout.write(f'{key}: {cfg[key]}')
        self.stdout.write('checkout_mode: MANAGER (онлайн-оплата для оформления не нужна)')
        if not settings.STAFF_NOTIFICATION_EMAILS:
            self.stdout.write(self.style.WARNING('Email менеджера не настроен. Заказы всё равно видны в /ru/staff/orders/.'))
        slug = options.get('event')
        if not slug:
            return
        try:
            event = Event.objects.select_related('category').get(slug=slug)
        except Event.DoesNotExist:
            raise CommandError('Мероприятие с таким slug не найдено.')
        try:
            check_orderable(event, timezone.now())
        except BusinessError as exc:
            self.stdout.write(self.style.ERROR(f'{exc.business_code}: {exc.detail}'))
        else:
            self.stdout.write(self.style.SUCCESS('Приём заказа на мероприятие разрешён.'))
        count = available_units(event).count()
        self.stdout.write(f'Доступных TicketUnit с ценой: {count}')
        self.stdout.write('Точки на схеме без TicketUnit — не остаток билетов. Даже при старом режиме REQUEST реальный доступный остаток с ценой можно оформить.')
