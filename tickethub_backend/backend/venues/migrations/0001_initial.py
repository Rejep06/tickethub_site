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
            name='Venue',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name_ru', models.CharField(max_length=200)),
                ('name_en', models.CharField(max_length=200)),
                ('country', models.CharField(max_length=2)),
                ('city', models.CharField(max_length=100)),
                ('city_en', models.CharField(max_length=100, blank=True)),
                ('address', models.CharField(max_length=300)),
                ('address_en', models.CharField(max_length=300, blank=True)),
                ('timezone', models.CharField(max_length=64, default='Europe/Moscow')),
            ],
            options={'abstract': False},
        ),
        migrations.CreateModel(
            name='SeatingPlan',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('venue', models.ForeignKey('venues.venue', on_delete=models.PROTECT, related_name='plans')),
                ('name', models.CharField(max_length=200)),
                ('image', models.ImageField(upload_to='plans/', blank=True)),
                ('rights_source', models.CharField(max_length=500, blank=True)),
                ('rights_confirmed', models.BooleanField(default=False)),
                ('version', models.PositiveIntegerField(default=1)),
                ('status', models.CharField(max_length=10, default='DRAFT', choices=[('DRAFT', 'Draft'), ('PUBLISHED', 'Published'), ('ARCHIVED', 'Archived')])),
            ],
            options={'abstract': False},
        ),
        migrations.CreateModel(
            name='Seat',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('plan', models.ForeignKey('venues.seatingplan', on_delete=models.PROTECT, related_name='seats')),
                ('sector', models.CharField(max_length=50)),
                ('row', models.CharField(max_length=30)),
                ('number', models.CharField(max_length=30)),
                ('x', models.DecimalField(max_digits=7, decimal_places=6)),
                ('y', models.DecimalField(max_digits=7, decimal_places=6)),
                ('adjacency_group', models.CharField(max_length=80, blank=True)),
                ('adjacency_position', models.PositiveIntegerField(null=True, blank=True)),
            ],
            options={'ordering': ['sector', 'row', 'number', 'id']},
        ),
    ]
