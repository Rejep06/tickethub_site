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
            name='Category',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('slug', models.SlugField(unique=True)),
                ('name_ru', models.CharField(max_length=100)),
                ('name_en', models.CharField(max_length=100)),
                ('kind', models.CharField(max_length=7, choices=[('SPORT', 'Sport'), ('CONCERT', 'Concert'), ('OTHER', 'Other')])),
                ('parent', models.ForeignKey('events.category', on_delete=models.PROTECT, null=True, blank=True, related_name='children')),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
            ],
            options={'ordering': ['sort_order', 'name_ru', 'id']},
        ),
        migrations.CreateModel(
            name='Participant',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name_ru', models.CharField(max_length=200)),
                ('name_en', models.CharField(max_length=200)),
                ('kind', models.CharField(max_length=10, choices=[('TEAM', 'Team'), ('ARTIST', 'Artist'), ('OTHER', 'Other')])),
            ],
            options={'abstract': False},
        ),
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('slug', models.SlugField(unique=True, max_length=200)),
                ('title_ru', models.CharField(max_length=250)),
                ('title_en', models.CharField(max_length=250)),
                ('description_ru', models.TextField(blank=True)),
                ('description_en', models.TextField(blank=True)),
                ('category', models.ForeignKey('events.category', on_delete=models.PROTECT, related_name='events')),
                ('participants', models.ManyToManyField('events.participant', blank=True, related_name='events')),
                ('start_at', models.DateTimeField(null=True, blank=True, db_index=True)),
                ('date_tba', models.BooleanField(default=False)),
                ('sale_deadline', models.DateTimeField(null=True, blank=True)),
                ('status', models.CharField(max_length=10, default='SCHEDULED', db_index=True, choices=[('SCHEDULED', 'Scheduled'), ('POSTPONED', 'Postponed'), ('CANCELLED', 'Cancelled'), ('FINISHED', 'Finished')])),
                ('visibility', models.CharField(max_length=8, default='PUBLIC', choices=[('PUBLIC', 'Public'), ('UNLISTED', 'Unlisted')])),
                ('is_published', models.BooleanField(default=False, db_index=True)),
                ('image', models.ImageField(upload_to='events/', blank=True)),
                ('image_rights_source', models.CharField(max_length=500, blank=True)),
                ('image_rights_confirmed', models.BooleanField(default=False)),
                ('fan_id_required', models.BooleanField(null=True, default=None)),
                ('fan_id_description_ru', models.TextField(blank=True)),
                ('fan_id_description_en', models.TextField(blank=True)),
                ('refund_policy_ru', models.TextField(blank=True)),
                ('refund_policy_en', models.TextField(blank=True)),
                ('refund_policy_approved', models.BooleanField(default=False)),
                ('late_delivery_due_at', models.DateTimeField(null=True, blank=True)),
                ('version', models.PositiveIntegerField(default=1)),
            ],
            options={'ordering': ['start_at', 'id']},
        ),
    ]
