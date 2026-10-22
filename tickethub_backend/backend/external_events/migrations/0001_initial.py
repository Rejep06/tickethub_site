# Authored from model declarations. Validate on PostgreSQL before deployment.
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('venues', '0003_external_place'),
        ('events', '0002_relations_and_constraints'),
    ]
    operations = [
        migrations.CreateModel(name='ExternalEvent', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('provider', models.CharField(max_length=20, default='portalbilet', editable=False)),
            ('external_event_id', models.CharField(max_length=30, editable=False)),
            ('event_source_id', models.CharField(max_length=30, editable=False)),
            ('external_place_id', models.CharField(max_length=30, editable=False)),
            ('external_layout_id', models.CharField(max_length=30, blank=True, editable=False)),
            ('url', models.URLField(max_length=600)),
            ('title', models.CharField(max_length=250)),
            ('venue', models.ForeignKey('venues.venue', on_delete=models.PROTECT, null=True, blank=True)),
            ('status', models.CharField(max_length=12, default='NEW', choices=[('NEW', 'New'), ('RUNNING', 'Running'), ('PARTIAL', 'Partial'), ('FAILED', 'Failed')])),
            ('last_attempt_at', models.DateTimeField(null=True, blank=True)),
            ('last_metadata_sync_at', models.DateTimeField(null=True, blank=True)),
            ('diagnostics', models.JSONField(default=dict, blank=True)),
        ], options={'ordering': ['-updated_at'], 'constraints': [models.UniqueConstraint(fields=['provider', 'external_event_id'], name='external_event_source_unique')]}),
        migrations.CreateModel(name='ExternalDate', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('external_event', models.ForeignKey('external_events.externalevent', on_delete=models.PROTECT, related_name='dates')),
            ('external_date_id', models.CharField(max_length=30, editable=False)),
            ('event', models.OneToOneField('events.event', on_delete=models.PROTECT, related_name='external_date')),
            ('source_active', models.BooleanField(default=True)),
            ('source_start_at', models.DateTimeField(null=True, blank=True)),
            ('last_local_version', models.PositiveIntegerField(default=1)),
            ('last_seen_at', models.DateTimeField()),
        ], options={'constraints': [models.UniqueConstraint(fields=['external_event', 'external_date_id'], name='external_date_source_unique')]}),
        migrations.CreateModel(name='ExternalSnapshot', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('external_event', models.ForeignKey('external_events.externalevent', on_delete=models.CASCADE, related_name='snapshots')),
            ('resource', models.CharField(max_length=90)),
            ('url', models.URLField(max_length=1000)),
            ('sha256', models.CharField(max_length=64)),
            ('byte_count', models.PositiveIntegerField()),
            ('structure', models.JSONField(default=dict)),
            ('payload', models.JSONField(null=True, blank=True)),
        ], options={'constraints': [models.UniqueConstraint(fields=['external_event', 'resource'], name='external_snapshot_resource_unique')]}),
    ]
