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
            name='TicketRequest',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('number', models.CharField(max_length=25, unique=True, default=request_number, editable=False)),
                ('custom_event_name', models.CharField(max_length=250, blank=True)),
                ('city', models.CharField(max_length=100, blank=True)),
                ('desired_date', models.DateField(null=True, blank=True)),
                ('quantity', models.PositiveSmallIntegerField()),
                ('preferences', models.CharField(max_length=500, blank=True)),
                ('together_required', models.BooleanField(default=False)),
                ('budget_minor', models.PositiveBigIntegerField(null=True, blank=True)),
                ('comment', models.TextField(blank=True, max_length=2000)),
                ('status', models.CharField(max_length=11, default='NEW', choices=[('NEW', 'New'), ('IN_PROGRESS', 'In progress'), ('OFFERED', 'Offered'), ('CONVERTED', 'Converted'), ('CANCELLED', 'Cancelled'), ('REJECTED', 'Rejected')])),
                ('customer_name', models.CharField(max_length=100)),
                ('customer_phone', models.CharField(max_length=16)),
                ('customer_email', models.EmailField()),
                ('internal_notes', models.TextField(blank=True)),
                ('public_response', models.TextField(blank=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('idempotency_key', models.UUIDField()),
                ('request_hash', models.CharField(max_length=64)),
                ('analytics_session_key', models.CharField(max_length=64, blank=True)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name='Quote',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ticket_request', models.ForeignKey('ticket_requests.ticketrequest', on_delete=models.PROTECT, related_name='quotes')),
                ('version', models.PositiveIntegerField(default=1)),
                ('status', models.CharField(max_length=9, default='DRAFT', choices=[('DRAFT', 'Draft'), ('SENT', 'Sent'), ('ACCEPTED', 'Accepted'), ('EXPIRED', 'Expired'), ('WITHDRAWN', 'Withdrawn')])),
                ('expires_at', models.DateTimeField()),
                ('total_minor', models.PositiveBigIntegerField()),
                ('public_comment', models.TextField(blank=True, max_length=2000)),
                ('sent_at', models.DateTimeField(null=True, blank=True)),
                ('together_confirmed', models.BooleanField(default=False)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name='QuoteItem',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('quote', models.ForeignKey('ticket_requests.quote', on_delete=models.PROTECT, related_name='items')),
                ('price_minor', models.PositiveBigIntegerField()),
                ('name_ru', models.CharField(max_length=200)),
                ('name_en', models.CharField(max_length=200)),
                ('sector', models.CharField(max_length=50, blank=True)),
                ('row', models.CharField(max_length=30, blank=True)),
                ('seat_number', models.CharField(max_length=30, blank=True)),
            ],
            options={},
        ),
    ]
