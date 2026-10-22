import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('external_events', '0001_initial'),
        ('venues', '0004_external_layout'),
    ]
    operations = [
        migrations.AlterField(
            model_name='externalevent',
            name='status',
            field=models.CharField(max_length=12, default='NEW', choices=[
                ('NEW', 'New'), ('RUNNING', 'Running'), ('COMPLETED', 'Completed'),
                ('PARTIAL', 'Partial'), ('FAILED', 'Failed'),
            ]),
        ),
        migrations.CreateModel(
            name='ExternalSeatInventory',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('external_ticket_id', models.CharField(max_length=100, blank=True, default='')),
                ('source_price_minor', models.PositiveBigIntegerField()),
                ('currency', models.CharField(max_length=3, default='RUB')),
                ('source_code', models.CharField(max_length=50, blank=True, default='')),
                ('source_available', models.BooleanField(default=True)),
                ('enabled_for_sale', models.BooleanField(default=False)),
                ('last_seen_at', models.DateTimeField()),
                ('external_date', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='seat_inventory', to='external_events.externaldate')),
                ('seat', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='external_inventory', to='venues.seat')),
            ],
        ),
        migrations.AddConstraint(
            model_name='externalseatinventory',
            constraint=models.UniqueConstraint(fields=['external_date', 'seat'], name='external_date_seat_unique'),
        ),
        migrations.AddIndex(
            model_name='externalseatinventory',
            index=models.Index(fields=['external_date', 'source_available'], name='external_seat_avail_idx'),
        ),
        migrations.CreateModel(
            name='ExternalStandingInventory',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('external_key', models.CharField(max_length=64, editable=False)),
                ('name', models.CharField(max_length=200)),
                ('external_ticket_id', models.CharField(max_length=100, blank=True, default='')),
                ('source_price_minor', models.PositiveBigIntegerField()),
                ('currency', models.CharField(max_length=3, default='RUB')),
                ('source_code', models.CharField(max_length=50, blank=True, default='')),
                ('available_count', models.PositiveIntegerField(default=0)),
                ('source_available', models.BooleanField(default=True)),
                ('enabled_for_sale', models.BooleanField(default=False)),
                ('last_seen_at', models.DateTimeField()),
                ('external_date', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='standing_inventory', to='external_events.externaldate')),
            ],
        ),
        migrations.AddConstraint(
            model_name='externalstandinginventory',
            constraint=models.UniqueConstraint(fields=['external_date', 'external_key'], name='external_standing_key_unique'),
        ),
        migrations.AddIndex(
            model_name='externalstandinginventory',
            index=models.Index(fields=['external_date', 'source_available'], name='external_stand_avail_idx'),
        ),
    ]
