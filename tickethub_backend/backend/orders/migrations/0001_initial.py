# Authored offline from the model field declarations; not Django-generated.
# Must pass makemigrations --check --dry-run and a clean PostgreSQL migrate.
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
from core.identifiers import order_number, request_number


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('number', models.CharField(max_length=25, unique=True, default=order_number, editable=False)),
                ('origin', models.CharField(max_length=12, choices=[('SITE_DIRECT', 'Site direct'), ('SITE_REQUEST', 'Site request')])),
                ('order_state', models.CharField(max_length=11, default='NEW', choices=[('NEW', 'New'), ('IN_PROGRESS', 'In progress'), ('CONFIRMED', 'Confirmed'), ('COMPLETED', 'Completed'), ('REJECTED', 'Rejected'), ('CANCELLED', 'Cancelled')])),
                ('customer_name', models.CharField(max_length=100)),
                ('customer_phone', models.CharField(max_length=16)),
                ('customer_email', models.EmailField()),
                ('customer_comment', models.TextField(blank=True, max_length=2000)),
                ('fan_id_answer', models.CharField(max_length=12, blank=True, choices=[('HAS_FAN_ID', 'Has Fan ID'), ('NEEDS_HELP', 'Needs help'), ('NOT_SURE', 'Not sure')])),
                ('fan_id_help_state', models.CharField(max_length=12, default='NOT_NEEDED', choices=[('NOT_NEEDED', 'Not needed'), ('REQUESTED', 'Requested'), ('IN_PROGRESS', 'In progress'), ('INSTRUCTED', 'Instructed')])),
                ('total_minor', models.PositiveBigIntegerField()),
                ('event_snapshot', models.JSONField(default=dict)),
                ('accepted_document_versions', models.JSONField(default=dict)),
                ('review_due_at', models.DateTimeField()),
                ('settlement_due_at', models.DateTimeField(null=True, blank=True)),
                ('delivery_due_at', models.DateTimeField()),
                ('first_contact_at', models.DateTimeField(null=True, blank=True)),
                ('confirmed_at', models.DateTimeField(null=True, blank=True)),
                ('first_paid_at', models.DateTimeField(null=True, blank=True)),
                ('internal_notes', models.TextField(blank=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('idempotency_key', models.UUIDField()),
                ('request_hash', models.CharField(max_length=64)),
                ('analytics_session_key', models.CharField(max_length=64, blank=True)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('order', models.ForeignKey('orders.order', on_delete=models.PROTECT, related_name='items')),
                ('name_ru', models.CharField(max_length=200)),
                ('name_en', models.CharField(max_length=200)),
                ('sector', models.CharField(max_length=50, blank=True)),
                ('row', models.CharField(max_length=30, blank=True)),
                ('seat_number', models.CharField(max_length=30, blank=True)),
                ('sale_price_minor', models.PositiveBigIntegerField()),
                ('purchase_price_minor', models.PositiveBigIntegerField(null=True, blank=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name='CustomerCase',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('order', models.ForeignKey('orders.order', on_delete=models.PROTECT, related_name='cases')),
                ('kind', models.CharField(max_length=14, default='REFUND_REQUEST', choices=[('REFUND_REQUEST', 'Refund'), ('CANCEL_REQUEST', 'Cancel'), ('DELIVERY_ISSUE', 'Delivery issue'), ('OTHER', 'Other')])),
                ('items', models.ManyToManyField('orders.orderitem', related_name='cases')),
                ('reason', models.TextField(max_length=2000)),
                ('requested_minor', models.PositiveBigIntegerField(null=True, blank=True)),
                ('approved_minor', models.PositiveBigIntegerField(null=True, blank=True)),
                ('status', models.CharField(max_length=11, default='NEW', choices=[('NEW', 'New'), ('IN_PROGRESS', 'In progress'), ('NEED_INFO', 'Need info'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('CLOSED', 'Closed')])),
                ('public_response', models.TextField(blank=True)),
                ('internal_notes', models.TextField(blank=True)),
                ('decided_at', models.DateTimeField(null=True, blank=True)),
                ('version', models.PositiveIntegerField(default=1)),
            ],
            options={'abstract': False},
        ),
        migrations.CreateModel(
            name='DeliveryRecord',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('order', models.ForeignKey('orders.order', on_delete=models.PROTECT, related_name='deliveries')),
                ('items', models.ManyToManyField('orders.orderitem', related_name='deliveries')),
                ('recipient_email', models.EmailField()),
                ('sent_at', models.DateTimeField()),
                ('note', models.TextField(blank=True)),
                ('message_id', models.CharField(max_length=200, blank=True)),
                ('status', models.CharField(max_length=6, default='SENT', choices=[('SENT', 'Sent'), ('VOIDED', 'Voided')])),
                ('void_reason', models.TextField(blank=True)),
                ('voided_at', models.DateTimeField(null=True, blank=True)),
                ('idempotency_key', models.UUIDField()),
                ('request_hash', models.CharField(max_length=64)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name='OrderHistory',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('order', models.ForeignKey('orders.order', on_delete=models.PROTECT, related_name='history')),
                ('event_type', models.CharField(max_length=40)),
                ('public_message', models.CharField(max_length=500)),
                ('internal_note', models.TextField(blank=True)),
            ],
            options={'ordering': ['created_at', 'id']},
        ),
    ]
