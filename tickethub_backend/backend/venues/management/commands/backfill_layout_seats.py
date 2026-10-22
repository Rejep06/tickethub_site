from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.errors import BusinessError
from venues.models import SeatingPlan
from venues.import_geometry import materialize_geometry


class Command(BaseCommand):
    help = 'Создать все места из уже сохранённой геометрии PortalBilet, без HTTP и без создания билетов.'

    def add_arguments(self, parser):
        parser.add_argument('--plan', help='UUID одной схемы; по умолчанию все импортированные схемы.')

    def handle(self, *args, **options):
        plans = SeatingPlan.objects.filter(external_provider='portalbilet').order_by('id')
        if options['plan']:
            plans = plans.filter(pk=options['plan'])
        for pk in plans.values_list('pk', flat=True).iterator():
            try:
                with transaction.atomic():
                    plan = SeatingPlan.objects.select_for_update().get(pk=pk)
                    created = materialize_geometry(plan)
                    total = plan.seats.count()
                    unknown = plan.seats.filter(sector='', row='', number='').count()
                self.stdout.write(f'{pk}: added={created}; total={total}; labels_unknown={unknown}')
            except (BusinessError, ValueError) as exc:
                raise CommandError(f'Схема {pk}: {exc}. Эта схема не изменена.') from exc
