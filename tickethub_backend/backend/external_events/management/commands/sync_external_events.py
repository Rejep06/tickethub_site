from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from core.errors import BusinessError
from external_events.http import ProviderError
from external_events.models import ExternalEvent
from external_events.services import sync_source


class Command(BaseCommand):
    help = 'Синхронизировать источники по расписанию; не создаёт внешних резервов/билетов.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, choices=range(1, 101), default=5)
        parser.add_argument('--force', action='store_true')

    def handle(self, *args, **options):
        query = ExternalEvent.objects.order_by('last_attempt_at', 'id')
        if not options['force']:
            query = query.filter(last_attempt_at__lt=timezone.now() - timedelta(minutes=settings.PORTALBILET_SYNC_MINUTES))
        failures = 0
        for source in list(query[:options['limit']]):
            try:
                result = sync_source(source.pk, actor=None)
                self.stdout.write(f'{source.pk}: {result["status"]}')
                if result['status'] == 'FAILED':
                    failures += 1
            except (ProviderError, BusinessError) as exc:
                failures += 1
                ExternalEvent.objects.filter(pk=source.pk).update(last_attempt_at=timezone.now())
                self.stderr.write(f'{source.pk}: {exc}')
        if failures:
            raise CommandError(f'Неудачных синхронизаций: {failures}. Проверьте диагностику.')
