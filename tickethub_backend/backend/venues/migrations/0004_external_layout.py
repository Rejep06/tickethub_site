from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('venues', '0003_external_place')]
    operations = [
        migrations.AddField(model_name='seatingplan', name='external_provider', field=models.CharField(max_length=20, blank=True, default='', editable=False)),
        migrations.AddField(model_name='seatingplan', name='external_layout_id', field=models.CharField(max_length=30, blank=True, default='', editable=False)),
        migrations.AddField(model_name='seatingplan', name='external_background_url', field=models.URLField(max_length=1000, blank=True, default='', editable=False)),
        migrations.AddField(model_name='seatingplan', name='external_width', field=models.PositiveIntegerField(null=True, blank=True, editable=False)),
        migrations.AddField(model_name='seatingplan', name='external_height', field=models.PositiveIntegerField(null=True, blank=True, editable=False)),
        migrations.AddField(model_name='seatingplan', name='external_geometry', field=models.JSONField(default=list, blank=True, editable=False)),
        migrations.AddField(model_name='seatingplan', name='external_sectors', field=models.JSONField(default=list, blank=True, editable=False)),
        migrations.AddField(model_name='seatingplan', name='external_synced_at', field=models.DateTimeField(null=True, blank=True, editable=False)),
        migrations.AddConstraint(model_name='seatingplan', constraint=models.UniqueConstraint(
            fields=['external_provider', 'external_layout_id'],
            condition=~models.Q(external_provider='') & ~models.Q(external_layout_id=''),
            name='plan_external_layout_unique')),
    ]
