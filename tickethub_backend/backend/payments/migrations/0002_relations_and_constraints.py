# Authored offline from the model field declarations; not Django-generated.
# Must pass makemigrations --check --dry-run and a clean PostgreSQL migrate.
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
from core.identifiers import order_number, request_number


class Migration(migrations.Migration):
    dependencies = [('payments', '0001_initial'), ('orders', '0001_initial'), ('users', '0001_initial')]
    operations = [
        migrations.AddField(model_name='financialentry', name='order', field=models.ForeignKey('orders.order', on_delete=models.PROTECT, related_name='financial_entries')),
        migrations.AddField(model_name='financialentry', name='created_by', field=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)),
        migrations.AddField(model_name='financialentry', name='refund_case', field=models.ForeignKey('orders.customercase', on_delete=models.PROTECT, null=True, blank=True, related_name='financial_entries')),
        migrations.AddConstraint(model_name='financialentry', constraint=models.CheckConstraint(condition=Q(amount_minor__gt=0), name='financial_positive_amount')),
        migrations.AddConstraint(model_name='financialentry', constraint=models.CheckConstraint(condition=Q(direction='NORMAL', reversal_of__isnull=True) | Q(direction='REVERSAL', reversal_of__isnull=False), name='financial_reversal_link')),
        migrations.AddConstraint(model_name='financialentry', constraint=models.CheckConstraint(condition=Q(kind='CUSTOMER_REFUND', refund_case__isnull=False) | ~Q(kind='CUSTOMER_REFUND') & Q(refund_case__isnull=True), name='financial_refund_case_link')),
        migrations.AddConstraint(model_name='financialentry', constraint=models.UniqueConstraint(fields=['order', 'idempotency_key'], name='financial_idempotency_unique')),
    ]
