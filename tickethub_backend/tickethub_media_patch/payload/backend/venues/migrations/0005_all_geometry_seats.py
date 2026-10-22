from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('venues', '0004_external_layout')]
    operations = [
        migrations.AddField(model_name='seat', name='external_point_key',
            field=models.CharField(max_length=64, blank=True, default='', editable=False)),
        migrations.AlterField(model_name='seat', name='sector', field=models.CharField(max_length=50, blank=True)),
        migrations.AlterField(model_name='seat', name='row', field=models.CharField(max_length=30, blank=True)),
        migrations.AlterField(model_name='seat', name='number', field=models.CharField(max_length=30, blank=True)),
        migrations.RemoveConstraint(model_name='seat', name='seat_plan_position_unique'),
        migrations.AddConstraint(model_name='seat', constraint=models.UniqueConstraint(
            fields=['plan', 'sector', 'row', 'number'],
            condition=~models.Q(sector='') & ~models.Q(row='') & ~models.Q(number=''),
            name='seat_plan_position_unique')),
        migrations.AddConstraint(model_name='seat', constraint=models.UniqueConstraint(
            fields=['plan', 'external_point_key'], condition=~models.Q(external_point_key=''),
            name='seat_plan_external_point_unique')),
        migrations.AddConstraint(model_name='seat', constraint=models.CheckConstraint(condition=(
            (~models.Q(sector='') & ~models.Q(row='') & ~models.Q(number='')) |
            (models.Q(sector='', row='', number='') & ~models.Q(external_point_key=''))
        ), name='seat_labels_complete_or_unknown')),
    ]
