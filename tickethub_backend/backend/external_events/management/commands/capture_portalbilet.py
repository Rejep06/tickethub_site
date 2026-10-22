from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from external_events.capture import capture
from external_events.http import ProviderError


class Command(BaseCommand):
    help = 'Сохранить реальные JSON PortalBilet и ZIP для проверки формата, без изменения БД.'

    def add_arguments(self, parser):
        parser.add_argument('--url', required=True)
        parser.add_argument('--output', default=str(settings.BASE_DIR / 'portalbilet_capture'))
        parser.add_argument('--max-dates', type=int, choices=range(1, 21), default=2)

    def handle(self, *args, **options):
        try:
            report, archive = capture(options['url'], options['output'], options['max_dates'])
        except (ProviderError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f'{report["status"]}: {archive}')
        for error in report['errors']:
            self.stderr.write(f'{error["resource"]}: {error["code"]} — {error["message"]}')
        if report['errors']:
            raise CommandError('Часть ответов недоступна. Диагностика сохранена в архиве.')
