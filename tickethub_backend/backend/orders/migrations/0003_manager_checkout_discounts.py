"""Add immutable pricing snapshots; existing orders keep their original totals."""
from django.db import migrations, models
from django.db.models import F, Q


def backfill_prices(apps, schema_editor):
    alias = schema_editor.connection.alias
    apps.get_model('orders', 'Order').objects.using(alias).update(subtotal_minor=F('total_minor'))
    apps.get_model('orders', 'OrderItem').objects.using(alias).update(original_price_minor=F('sale_price_minor'))


class Migration(migrations.Migration):
    dependencies = [('orders', '0002_relations_and_constraints')]
    operations = [
        migrations.AddField(model_name='order', name='subtotal_minor', field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name='order', name='discount_minor', field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name='order', name='promo_code', field=models.CharField(blank=True, default='', max_length=40)),
        migrations.AddField(model_name='orderitem', name='original_price_minor', field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name='orderitem', name='discount_minor', field=models.PositiveBigIntegerField(default=0)),
        migrations.AlterField(model_name='order', name='delivery_due_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.RunPython(backfill_prices, migrations.RunPython.noop),
        migrations.AddConstraint(model_name='order', constraint=models.CheckConstraint(
            condition=Q(subtotal_minor=F('total_minor') + F('discount_minor')), name='order_discount_matches_total')),
        migrations.AddConstraint(model_name='orderitem', constraint=models.CheckConstraint(
            condition=Q(original_price_minor=F('sale_price_minor') + F('discount_minor')), name='order_item_discount_matches')),
    ]
