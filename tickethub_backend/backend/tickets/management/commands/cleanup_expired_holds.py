from django.core.management.base import BaseCommand
from tickets.services import cleanup_expired_holds


class Command(BaseCommand):
    help = 'Освобождает только истёкшие checkout-резервы. Заказы не освобождаются.'

    def handle(self, *args, **options):
        count = cleanup_expired_holds()
        self.stdout.write(f'Expired checkouts cleaned: {count}')
