# Authored offline from the model field declarations; not Django-generated.
# Must pass makemigrations --check --dry-run and a clean PostgreSQL migrate.
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
from core.identifiers import order_number, request_number


class Migration(migrations.Migration):
    dependencies = [('orders', '0001_initial'), ('events', '0001_initial'), ('ticket_requests', '0001_initial'), ('tickets', '0001_initial'), ('users', '0001_initial')]
    operations = [
        migrations.AddField(model_name='order', name='user', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')),
        migrations.AddField(model_name='order', name='event', field=models.ForeignKey('events.event', on_delete=models.PROTECT, related_name='orders')),
        migrations.AddField(model_name='order', name='hold', field=models.OneToOneField('tickets.checkouthold', on_delete=models.PROTECT, related_name='order')),
        migrations.AddField(model_name='order', name='quote', field=models.OneToOneField('ticket_requests.quote', on_delete=models.PROTECT, null=True, blank=True, related_name='order')),
        migrations.AddField(model_name='order', name='ticket_request', field=models.ForeignKey('ticket_requests.ticketrequest', on_delete=models.PROTECT, null=True, blank=True, related_name='orders')),
        migrations.AddField(model_name='order', name='manager', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='managed_orders')),
        migrations.AddField(model_name='orderitem', name='ticket_unit', field=models.ForeignKey('tickets.ticketunit', on_delete=models.PROTECT, related_name='order_items')),
        migrations.AddField(model_name='customercase', name='user', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)),
        migrations.AddField(model_name='customercase', name='decided_by', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='case_decisions')),
        migrations.AddField(model_name='deliveryrecord', name='sent_by', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)),
        migrations.AddField(model_name='orderhistory', name='actor', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)),
        migrations.AddConstraint(model_name='order', constraint=models.UniqueConstraint(fields=['user', 'idempotency_key'], name='order_idempotency_unique')),
        migrations.AddConstraint(model_name='order', constraint=models.UniqueConstraint(fields=['user', 'event'], condition=Q(order_state__in=['NEW', 'IN_PROGRESS']), name='order_one_unprocessed')),
        migrations.AddConstraint(model_name='order', constraint=models.CheckConstraint(condition=Q(total_minor__gt=0), name='order_positive_total')),
        migrations.AddConstraint(model_name='orderitem', constraint=models.UniqueConstraint(fields=['order', 'ticket_unit'], name='order_unit_unique')),
        migrations.AddConstraint(model_name='orderitem', constraint=models.UniqueConstraint(fields=['ticket_unit'], condition=Q(is_active=True), name='unit_one_active_order_item')),
        migrations.AddConstraint(model_name='deliveryrecord', constraint=models.UniqueConstraint(fields=['order', 'idempotency_key'], name='delivery_idempotency_unique')),
        migrations.AddIndex(model_name='order', index=models.Index(fields=['user', 'created_at'], name='order_customer_idx')),
        migrations.AddIndex(model_name='order', index=models.Index(fields=['order_state', 'created_at'], name='order_queue_idx')),
        migrations.AddIndex(model_name='order', index=models.Index(fields=['delivery_due_at'], name='order_delivery_due_idx')),
    ]
