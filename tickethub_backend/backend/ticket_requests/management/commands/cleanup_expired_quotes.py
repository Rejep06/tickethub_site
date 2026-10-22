from django.core.management.base import BaseCommand
from ticket_requests.services import cleanup_expired_quotes


class Command(BaseCommand):
    help = 'Обновляет состояния истёкших предложений. API проверяет срок и без этой команды.'

    def handle(self, *args, **options):
        self.stdout.write(f'Expired quotes cleaned: {cleanup_expired_quotes()}')
