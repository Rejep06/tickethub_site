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
            name='FinancialEntry',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('kind', models.CharField(max_length=15, choices=[('PAYMENT', 'Payment'), ('CUSTOMER_REFUND', 'Customer refund'), ('DIRECT_EXPENSE', 'Direct expense'), ('SUPPLIER_REFUND', 'Supplier refund')])),
                ('amount_minor', models.PositiveBigIntegerField()),
                ('occurred_at', models.DateTimeField(db_index=True)),
                ('method', models.CharField(max_length=13, choices=[('BANK_CARD', 'Bank card'), ('SBP', 'SBP'), ('BANK_TRANSFER', 'Bank transfer'), ('CASH', 'Cash'), ('OTHER', 'Other')])),
                ('reference', models.CharField(max_length=200)),
                ('notes', models.TextField(blank=True)),
                ('direction', models.CharField(max_length=8, default='NORMAL', choices=[('NORMAL', 'Normal'), ('REVERSAL', 'Reversal')])),
                ('reversal_of', models.OneToOneField('payments.financialentry', on_delete=models.PROTECT, null=True, blank=True, related_name='reversal')),
                ('idempotency_key', models.UUIDField()),
                ('request_hash', models.CharField(max_length=64)),
            ],
            options={'ordering': ['occurred_at', 'created_at', 'id']},
        ),
    ]
