"""Create a minimal real taxonomy, never demonstration events or users."""
from django.core.management.base import BaseCommand
from django.db import transaction
from events.services import save_category
from events.models import Category


class Command(BaseCommand):
    help = 'Создать отсутствующие категории. Не изменяет уже существующие категории или события.'

    @transaction.atomic
    def handle(self, *args, **options):
        rows = [('football', 'Футбол', 'Football', 'SPORT'), ('hockey', 'Хоккей', 'Ice hockey', 'SPORT'),
                ('basketball', 'Баскетбол', 'Basketball', 'SPORT'), ('tennis', 'Теннис', 'Tennis', 'SPORT'),
                ('concerts', 'Концерты', 'Concerts', 'CONCERT'), ('shows', 'Шоу', 'Shows', 'OTHER'),
                ('theatre', 'Театр', 'Theatre', 'OTHER')]
        for rank, (slug, ru, en, kind) in enumerate(rows):
            if Category.objects.filter(slug=slug).exists():
                self.stdout.write(f'Оставлено без изменений: {slug}')
                continue
            save_category(None, dict(slug=slug, name_ru=ru, name_en=en, kind=kind, sort_order=rank * 10))
            self.stdout.write(self.style.SUCCESS(f'Создано: {ru}'))
