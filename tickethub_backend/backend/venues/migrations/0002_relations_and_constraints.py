# Authored offline from the model field declarations; not Django-generated.
# Must pass makemigrations --check --dry-run and a clean PostgreSQL migrate.
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
from core.identifiers import order_number, request_number


class Migration(migrations.Migration):
    dependencies = [('venues', '0001_initial')]
    operations = [
        migrations.AddConstraint(model_name='seat', constraint=models.UniqueConstraint(fields=['plan', 'sector', 'row', 'number'], name='seat_plan_position_unique')),
        migrations.AddConstraint(model_name='seat', constraint=models.CheckConstraint(condition=Q(x__gte=0, x__lte=1, y__gte=0, y__lte=1), name='seat_coordinates_normalized')),
    ]
