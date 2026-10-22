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
            name='Supplier',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('contact', models.CharField(max_length=500, blank=True)),
                ('notes', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={'abstract': False},
        ),
        migrations.CreateModel(
            name='TicketOffer',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name_ru', models.CharField(max_length=200)),
                ('name_en', models.CharField(max_length=200)),
                ('description_ru', models.TextField(blank=True)),
                ('description_en', models.TextField(blank=True)),
                ('sale_price_minor', models.PositiveBigIntegerField(null=True, blank=True)),
                ('kind', models.CharField(max_length=8, choices=[('SEAT', 'Seat'), ('CATEGORY', 'Category'), ('STANDING', 'Standing')])),
                ('mode', models.CharField(max_length=9, default='AVAILABLE', choices=[('AVAILABLE', 'Available'), ('REQUEST', 'Request')])),
                ('is_active', models.BooleanField(default=True)),
                ('version', models.PositiveIntegerField(default=1)),
            ],
            options={'abstract': False},
        ),
        migrations.CreateModel(
            name='CheckoutHold',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('status', models.CharField(max_length=9, default='ACTIVE', choices=[('ACTIVE', 'Active'), ('CONVERTED', 'Converted'), ('EXPIRED', 'Expired'), ('RELEASED', 'Released')])),
                ('selection', models.JSONField(default=dict)),
                ('total_minor', models.PositiveBigIntegerField()),
                ('event_version', models.PositiveIntegerField()),
            ],
            options={},
        ),
        migrations.CreateModel(
            name='TicketUnit',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('offer', models.ForeignKey('tickets.ticketoffer', on_delete=models.PROTECT, related_name='units')),
                ('supplier', models.ForeignKey('tickets.supplier', on_delete=models.PROTECT, null=True, blank=True)),
                ('purchase_price_minor', models.PositiveBigIntegerField(null=True, blank=True)),
                ('supplier_reference', models.CharField(max_length=200, blank=True, default='')),
                ('stock_basis', models.CharField(max_length=20, default='OWNED', choices=[('OWNED', 'Owned'), ('EXCLUSIVE_ALLOCATION', 'Exclusive allocation')])),
                ('allocation_until', models.DateTimeField(null=True, blank=True)),
                ('status', models.CharField(max_length=13, default='AVAILABLE', choices=[('AVAILABLE', 'Available'), ('CHECKOUT_HELD', 'Checkout held'), ('ORDER_HELD', 'Order held'), ('SOLD', 'Sold'), ('BLOCKED', 'Blocked')])),
                ('current_hold', models.ForeignKey('tickets.checkouthold', on_delete=models.PROTECT, null=True, blank=True, related_name='current_units')),
                ('internal_notes', models.TextField(blank=True)),
                ('version', models.PositiveIntegerField(default=1)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name='CheckoutHoldItem',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('hold', models.ForeignKey('tickets.checkouthold', on_delete=models.PROTECT, related_name='items')),
                ('ticket_unit', models.ForeignKey('tickets.ticketunit', on_delete=models.PROTECT, related_name='hold_items')),
                ('name_ru', models.CharField(max_length=200)),
                ('name_en', models.CharField(max_length=200)),
                ('sector', models.CharField(max_length=50, blank=True)),
                ('row', models.CharField(max_length=30, blank=True)),
                ('seat_number', models.CharField(max_length=30, blank=True)),
                ('sale_price_minor', models.PositiveBigIntegerField()),
            ],
            options={},
        ),
    ]
