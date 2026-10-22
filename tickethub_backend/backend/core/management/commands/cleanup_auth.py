from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from users.models import AuthChallenge, AuthRateLimit


class Command(BaseCommand):
    help = 'Удаляет старые истёкшие OTP и неактивные окна ограничений.'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=2)
        challenges, _ = AuthChallenge.objects.filter(expires_at__lt=cutoff).delete()
        buckets, _ = AuthRateLimit.objects.filter(window_start__lt=cutoff).delete()
        self.stdout.write(f'Deleted challenges={challenges}, limit buckets={buckets}')
