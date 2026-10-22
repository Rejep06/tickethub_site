# Authored from model declarations. Validate on PostgreSQL before deployment.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('venues', '0002_relations_and_constraints')]
    operations = [
        migrations.AlterField(model_name='venue', name='country', field=models.CharField(max_length=2, blank=True)),
        migrations.AlterField(model_name='venue', name='city', field=models.CharField(max_length=100, blank=True)),
        migrations.AlterField(model_name='venue', name='address', field=models.CharField(max_length=300, blank=True)),
        migrations.AddField(model_name='venue', name='external_provider', field=models.CharField(max_length=20, blank=True, default='', editable=False)),
        migrations.AddField(model_name='venue', name='external_place_id', field=models.CharField(max_length=30, blank=True, default='', editable=False)),
        migrations.AddConstraint(model_name='venue', constraint=models.UniqueConstraint(
            fields=['external_provider', 'external_place_id'],
            condition=~models.Q(external_provider='') & ~models.Q(external_place_id=''), name='venue_external_place_unique')),
    ]
