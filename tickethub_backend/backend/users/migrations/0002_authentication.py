# Authored offline from the model field declarations; not Django-generated.
# Must pass makemigrations --check --dry-run and a clean PostgreSQL migrate.
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
from core.identifiers import order_number, request_number


class Migration(migrations.Migration):
    dependencies = [('users', '0001_initial')]
    operations = [
        migrations.CreateModel(
            name='AuthChallenge',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('email', models.EmailField()),
                ('purpose', models.CharField(max_length=80, default='login')),
                ('nonce', models.UUIDField(default=uuid.uuid4)),
                ('code_hmac', models.CharField(max_length=64, blank=True)),
                ('issued_at', models.DateTimeField(null=True)),
                ('expires_at', models.DateTimeField(null=True)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('consumed_at', models.DateTimeField(null=True)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name='AuthRateLimit',
            fields=[
                ('key', models.CharField(max_length=64, primary_key=True, serialize=False)),
                ('window_start', models.DateTimeField()),
                ('count', models.PositiveIntegerField(default=0)),
            ],
            options={},
        ),
        migrations.AddConstraint(model_name='authchallenge', constraint=models.UniqueConstraint(fields=['email', 'purpose'], name='otp_email_purpose_unique')),
    ]
