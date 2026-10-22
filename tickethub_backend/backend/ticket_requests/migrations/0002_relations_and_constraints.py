# Authored offline from the model field declarations; not Django-generated.
# Must pass makemigrations --check --dry-run and a clean PostgreSQL migrate.
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
from core.identifiers import order_number, request_number


class Migration(migrations.Migration):
    dependencies = [('ticket_requests', '0001_initial'), ('events', '0001_initial'), ('tickets', '0001_initial'), ('users', '0001_initial')]
    operations = [
        migrations.AddField(model_name='ticketrequest', name='user', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ticket_requests')),
        migrations.AddField(model_name='ticketrequest', name='event', field=models.ForeignKey('events.event', on_delete=models.PROTECT, null=True, blank=True)),
        migrations.AddField(model_name='ticketrequest', name='manager', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='managed_requests')),
        migrations.AddField(model_name='quote', name='event', field=models.ForeignKey('events.event', on_delete=models.PROTECT, related_name='quotes')),
        migrations.AddField(model_name='quoteitem', name='ticket_unit', field=models.ForeignKey('tickets.ticketunit', on_delete=models.PROTECT)),
        migrations.AddConstraint(model_name='ticketrequest', constraint=models.UniqueConstraint(fields=['user', 'idempotency_key'], name='request_idempotency_unique')),
        migrations.AddConstraint(model_name='ticketrequest', constraint=models.CheckConstraint(condition=Q(quantity__gte=1, quantity__lte=100), name='request_quantity_valid')),
        migrations.AddConstraint(model_name='ticketrequest', constraint=models.CheckConstraint(condition=Q(event__isnull=False) | ~Q(custom_event_name='') | ~Q(comment=''), name='request_event_or_description')),
        migrations.AddConstraint(model_name='quote', constraint=models.UniqueConstraint(fields=['ticket_request', 'version'], name='quote_version_unique')),
        migrations.AddConstraint(model_name='quoteitem', constraint=models.UniqueConstraint(fields=['quote', 'ticket_unit'], name='quote_unit_unique')),
        migrations.AddConstraint(model_name='quoteitem', constraint=models.CheckConstraint(condition=Q(price_minor__gt=0), name='quote_positive_price')),
        migrations.AddIndex(model_name='ticketrequest', index=models.Index(fields=['status', 'created_at'], name='request_queue_idx')),
    ]
