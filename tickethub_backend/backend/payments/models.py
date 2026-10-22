from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from core.models import Record


class FinancialEntry(Record):
    order = models.ForeignKey('orders.Order', on_delete=models.PROTECT, related_name='financial_entries')
    kind = models.CharField(max_length=15, choices=[('PAYMENT', 'Payment'), ('CUSTOMER_REFUND', 'Customer refund'), ('DIRECT_EXPENSE', 'Direct expense'), ('SUPPLIER_REFUND', 'Supplier refund')])
    amount_minor = models.PositiveBigIntegerField()
    occurred_at = models.DateTimeField(db_index=True)
    method = models.CharField(max_length=13, choices=[('BANK_CARD', 'Bank card'), ('SBP', 'SBP'), ('BANK_TRANSFER', 'Bank transfer'), ('CASH', 'Cash'), ('OTHER', 'Other')])
    reference = models.CharField(max_length=200)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    notes = models.TextField(blank=True)
    direction = models.CharField(max_length=8, default='NORMAL', choices=[('NORMAL', 'Normal'), ('REVERSAL', 'Reversal')])
    reversal_of = models.OneToOneField('self', on_delete=models.PROTECT, null=True, blank=True, related_name='reversal')
    refund_case = models.ForeignKey('orders.CustomerCase', on_delete=models.PROTECT, null=True, blank=True, related_name='financial_entries')
    idempotency_key = models.UUIDField()
    request_hash = models.CharField(max_length=64)

    class Meta:
        ordering = ['occurred_at', 'created_at', 'id']
        constraints = [
            models.CheckConstraint(condition=Q(amount_minor__gt=0), name='financial_positive_amount'),
            models.CheckConstraint(condition=Q(direction='NORMAL', reversal_of__isnull=True) | Q(direction='REVERSAL', reversal_of__isnull=False), name='financial_reversal_link'),
            models.CheckConstraint(condition=Q(kind='CUSTOMER_REFUND', refund_case__isnull=False) | (~Q(kind='CUSTOMER_REFUND') & Q(refund_case__isnull=True)), name='financial_refund_case_link'),
            models.UniqueConstraint(fields=['order', 'idempotency_key'], name='financial_idempotency_unique'),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Проводки неизменяемы. Создайте сторно.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Финансовая история не удаляется.')
