"""Read-only checks for catalogue publishing and launch preparation."""
import json
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.utils import timezone
from events.models import Event, Category


class Command(BaseCommand):
    help = 'Проверить опубликованную афишу. Ничего не изменяет и не удаляет.'

    def add_arguments(self, parser):
        parser.add_argument('--strict', action='store_true', help='Ненулевой код выхода при блокерах публикации.')

    def handle(self, *args, **options):
        failures = 0
        events = Event.objects.filter(is_published=True).select_related('category', 'venue', 'seating_plan')
        count = events.count()
        for event in events:
            errors = {}
            try:
                event.full_clean()
            except ValidationError as exc:
                errors.update(exc.message_dict if hasattr(exc, 'message_dict') else {'event': exc.messages})
            if event.slug.startswith('demo-') or event.title_ru.lower().startswith('демо:'):
                errors['demo'] = ['Демонстрационное событие: снимите с публикации перед запуском.']
            if errors:
                failures += 1
                self.stdout.write(f'BLOCK {event.pk} {event.slug}: {json.dumps(errors, ensure_ascii=False)}')
            if not event.image:
                self.stdout.write(f'WARN {event.slug}: нет обложки.')
            if event.start_at and event.start_at < timezone.now() and event.status == 'SCHEDULED':
                self.stdout.write(f'WARN {event.slug}: дата в прошлом; проверьте статус или снимите с публикации.')
        for category in Category.objects.filter(is_active=True, image=''):
            self.stdout.write(f'WARN category/{category.slug}: нет фотографии, используется нейтральная карточка.')
        self.stdout.write(f'Опубликовано: {count}; блокеров: {failures}. Данные не изменены.')
        if options['strict'] and (failures or not count):
            raise CommandError('Перед запуском устраните BLOCK и опубликуйте хотя бы одно проверенное событие.')
