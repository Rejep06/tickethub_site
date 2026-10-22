# Authored offline from the model field declarations; not Django-generated.
# Must pass makemigrations --check --dry-run and a clean PostgreSQL migrate.
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
from core.identifiers import order_number, request_number


class Migration(migrations.Migration):
    dependencies = [('events', '0001_initial'), ('venues', '0001_initial')]
    operations = [
        migrations.AddField(model_name='event', name='venue', field=models.ForeignKey('venues.venue', on_delete=models.PROTECT, related_name='events')),
        migrations.AddField(model_name='event', name='seating_plan', field=models.ForeignKey('venues.seatingplan', on_delete=models.PROTECT, null=True, blank=True, related_name='events')),
        migrations.AddIndex(model_name='event', index=models.Index(fields=['is_published', 'status', 'start_at'], name='event_catalog_idx')),
    ]
