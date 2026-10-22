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
            name='ContentPage',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('slug', models.SlugField()),
                ('version', models.PositiveIntegerField(default=1)),
                ('title_ru', models.CharField(max_length=200)),
                ('title_en', models.CharField(max_length=200)),
                ('body_ru', models.TextField()),
                ('body_en', models.TextField()),
                ('is_published', models.BooleanField(default=False)),
                ('published_at', models.DateTimeField(null=True, blank=True)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name='ConsentRecord',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('page', models.ForeignKey('core.contentpage', on_delete=models.PROTECT)),
                ('source', models.CharField(max_length=20)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name='PrivacyRequest',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('kind', models.CharField(max_length=12, choices=[('ACCESS', 'Access'), ('CORRECT', 'Correct'), ('DELETE', 'Delete')])),
                ('comment', models.TextField(blank=True, max_length=2000)),
                ('status', models.CharField(max_length=12, default='NEW', choices=[('NEW', 'New'), ('IN_PROGRESS', 'In progress'), ('CLOSED', 'Closed')])),
                ('response', models.TextField(blank=True)),
            ],
            options={'abstract': False},
        ),
        migrations.CreateModel(
            name='EmailLog',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('recipient', models.EmailField()),
                ('subject', models.CharField(max_length=250)),
                ('body', models.TextField()),
                ('status', models.CharField(max_length=8, default='PENDING', choices=[('PENDING', 'Pending'), ('SENDING', 'Sending'), ('SENT', 'Sent'), ('FAILED', 'Failed')])),
                ('attempts', models.PositiveIntegerField(default=0)),
                ('sent_at', models.DateTimeField(null=True, blank=True)),
                ('object_id', models.UUIDField(null=True, blank=True)),
                ('error_code', models.CharField(max_length=40, blank=True)),
            ],
            options={'abstract': False},
        ),
        migrations.CreateModel(
            name='IdempotencyRecord',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('key', models.UUIDField()),
                ('request_hash', models.CharField(max_length=64)),
            ],
            options={},
        ),
    ]
