# Authored offline from the model field declarations; not Django-generated.
# Must pass makemigrations --check --dry-run and a clean PostgreSQL migrate.
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
from core.identifiers import order_number, request_number


class Migration(migrations.Migration):
    dependencies = [('analytics', '0001_initial'), ('events', '0001_initial'), ('orders', '0001_initial'), ('ticket_requests', '0001_initial'), ('users', '0001_initial')]
    operations = [
        migrations.AddField(model_name='funnelevent', name='user', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)),
        migrations.AddField(model_name='funnelevent', name='event', field=models.ForeignKey('events.event', on_delete=models.PROTECT, null=True, blank=True)),
        migrations.AddField(model_name='funnelevent', name='order', field=models.ForeignKey('orders.order', on_delete=models.PROTECT, null=True, blank=True, related_name='funnel_events')),
        migrations.AddField(model_name='funnelevent', name='ticket_request', field=models.ForeignKey('ticket_requests.ticketrequest', on_delete=models.PROTECT, null=True, blank=True, related_name='funnel_events')),
        migrations.AddConstraint(model_name='funnelevent', constraint=models.UniqueConstraint(fields=['order', 'event_type'], condition=Q(order__isnull=False, source='SERVER'), name='funnel_order_step_unique')),
        migrations.AddConstraint(model_name='funnelevent', constraint=models.UniqueConstraint(fields=['ticket_request', 'event_type'], condition=Q(ticket_request__isnull=False, order__isnull=True, source='SERVER'), name='funnel_request_step_unique')),
        migrations.AddIndex(model_name='funnelevent', index=models.Index(fields=['event_type', 'created_at'], name='funnel_period_idx')),
    ]
