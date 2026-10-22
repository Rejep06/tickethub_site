# Authored offline from the model field declarations; not Django-generated.
# Must pass makemigrations --check --dry-run and a clean PostgreSQL migrate.
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
from core.identifiers import order_number, request_number


class Migration(migrations.Migration):
    dependencies = [('tickets', '0001_initial'), ('events', '0001_initial'), ('ticket_requests', '0001_initial'), ('users', '0001_initial'), ('venues', '0001_initial')]
    operations = [
        migrations.AddField(model_name='ticketoffer', name='event', field=models.ForeignKey('events.event', on_delete=models.PROTECT, related_name='offers')),
        migrations.AddField(model_name='checkouthold', name='user', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='holds')),
        migrations.AddField(model_name='checkouthold', name='event', field=models.ForeignKey('events.event', on_delete=models.PROTECT, related_name='holds')),
        migrations.AddField(model_name='checkouthold', name='quote', field=models.ForeignKey('ticket_requests.quote', on_delete=models.PROTECT, null=True, blank=True, related_name='holds')),
        migrations.AddField(model_name='ticketunit', name='event', field=models.ForeignKey('events.event', on_delete=models.PROTECT, related_name='units')),
        migrations.AddField(model_name='ticketunit', name='seat', field=models.ForeignKey('venues.seat', on_delete=models.PROTECT, null=True, blank=True, related_name='units')),
        migrations.AddConstraint(model_name='checkouthold', constraint=models.UniqueConstraint(fields=['user', 'event'], condition=Q(status='ACTIVE'), name='hold_one_active_user_event')),
        migrations.AddConstraint(model_name='ticketunit', constraint=models.UniqueConstraint(fields=['event', 'seat'], condition=Q(seat__isnull=False), name='unit_event_seat_unique')),
        migrations.AddConstraint(model_name='ticketunit', constraint=models.UniqueConstraint(fields=['event', 'supplier', 'supplier_reference'], condition=~Q(supplier_reference='') & Q(supplier__isnull=False), name='unit_supplier_reference_unique')),
        migrations.AddConstraint(model_name='ticketunit', constraint=models.CheckConstraint(condition=Q(status='CHECKOUT_HELD', current_hold__isnull=False) | ~Q(status='CHECKOUT_HELD') & Q(current_hold__isnull=True), name='unit_hold_matches_state')),
        migrations.AddConstraint(model_name='checkoutholditem', constraint=models.UniqueConstraint(fields=['hold', 'ticket_unit'], name='hold_unit_unique')),
        migrations.AddIndex(model_name='checkouthold', index=models.Index(fields=['status', 'expires_at'], name='hold_cleanup_idx')),
        migrations.AddIndex(model_name='ticketunit', index=models.Index(fields=['event', 'status'], name='unit_availability_idx')),
    ]
