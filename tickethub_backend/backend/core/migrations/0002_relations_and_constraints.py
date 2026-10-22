# Authored offline from the model field declarations; not Django-generated.
# Must pass makemigrations --check --dry-run and a clean PostgreSQL migrate.
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
from core.identifiers import order_number, request_number


class Migration(migrations.Migration):
    dependencies = [('core', '0001_initial'), ('tickets', '0001_initial'), ('users', '0001_initial')]
    operations = [
        migrations.AddField(model_name='contentpage', name='approved_by', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)),
        migrations.AddField(model_name='consentrecord', name='user', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)),
        migrations.AddField(model_name='privacyrequest', name='user', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)),
        migrations.AddField(model_name='idempotencyrecord', name='user', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)),
        migrations.AddField(model_name='idempotencyrecord', name='hold', field=models.ForeignKey('tickets.checkouthold', on_delete=models.PROTECT)),
        migrations.AddConstraint(model_name='contentpage', constraint=models.UniqueConstraint(fields=['slug', 'version'], name='content_slug_version_unique')),
        migrations.AddConstraint(model_name='contentpage', constraint=models.UniqueConstraint(fields=['slug'], condition=Q(is_published=True), name='content_one_published')),
        migrations.AddConstraint(model_name='consentrecord', constraint=models.UniqueConstraint(fields=['user', 'page', 'source'], name='consent_unique')),
        migrations.AddConstraint(model_name='idempotencyrecord', constraint=models.UniqueConstraint(fields=['user', 'key'], name='hold_idempotency_key_unique')),
    ]
