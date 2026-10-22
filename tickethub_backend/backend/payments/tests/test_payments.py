import uuid
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.errors import BusinessError
from tests.factories import confirmed_order, order_fixture, manager, payment_data
from payments.models import FinancialEntry
from payments.services import record_payment, reverse_entry
from payments.selectors import money_summary
from orders.services import cancel_order


class PaymentTests(TestCase):
    def setUp(self):
        self.order, self.units, self.staff = confirmed_order()

    def test_unpaid(self):
        self.assertEqual(money_summary(self.order)['state'], 'UNPAID')

    def test_partial_payment(self):
        record_payment(self.order.id, self.staff, payment_data(self.order, 30000), uuid.uuid4())
        self.assertEqual(money_summary(self.order)['state'], 'PARTIAL')

    def test_full_payment_sells_units(self):
        record_payment(self.order.id, self.staff, payment_data(self.order), uuid.uuid4())
        self.assertEqual(money_summary(self.order)['state'], 'PAID')
        self.units[0].refresh_from_db()
        self.assertEqual(self.units[0].status, 'SOLD')

    def test_second_payment_completes_total(self):
        record_payment(self.order.id, self.staff, payment_data(self.order, 30000), uuid.uuid4())
        record_payment(self.order.id, self.staff, payment_data(self.order, 70000), uuid.uuid4())
        self.assertEqual(money_summary(self.order)['state'], 'PAID')

    def test_overpayment_rejected(self):
        with self.assertRaises(BusinessError):
            record_payment(self.order.id, self.staff, payment_data(self.order, self.order.total_minor+1), uuid.uuid4())

    def test_negative_money_rejected(self):
        with self.assertRaises(BusinessError):
            record_payment(self.order.id, self.staff, payment_data(self.order, -1), uuid.uuid4())

    def test_duplicate_payment_is_idempotent(self):
        data, key = payment_data(self.order), uuid.uuid4()
        first, _ = record_payment(self.order.id, self.staff, data, key)
        second, created = record_payment(self.order.id, self.staff, data, key)
        self.assertEqual(first.id, second.id)
        self.assertFalse(created)
        self.assertEqual(FinancialEntry.objects.count(), 1)

    def test_reversal_preserves_original(self):
        entry, _ = record_payment(self.order.id, self.staff, payment_data(self.order), uuid.uuid4())
        self.order.refresh_from_db()
        reverse_entry(entry.id, self.staff, {'expected_version': self.order.version, 'occurred_at': timezone.now(), 'reason': 'Wrong record'}, uuid.uuid4())
        self.assertEqual(FinancialEntry.objects.count(), 2)
        self.assertEqual(money_summary(self.order)['state'], 'UNPAID')
        entry.refresh_from_db()
        self.assertEqual(entry.amount_minor, self.order.total_minor)

    def test_financial_entry_cannot_be_edited(self):
        entry, _ = record_payment(self.order.id, self.staff, payment_data(self.order), uuid.uuid4())
        entry.amount_minor = 1
        with self.assertRaises(ValidationError):
            entry.save()

    def test_financial_entry_cannot_be_deleted(self):
        entry, _ = record_payment(self.order.id, self.staff, payment_data(self.order), uuid.uuid4())
        with self.assertRaises(ValidationError):
            entry.delete()

    def test_paid_cancel_does_not_release_stock(self):
        record_payment(self.order.id, self.staff, payment_data(self.order), uuid.uuid4())
        self.order.refresh_from_db()
        cancel_order(self.order.id, self.staff, self.order.version, 'Manual cancellation')
        self.units[0].refresh_from_db()
        self.assertEqual(self.units[0].status, 'BLOCKED')

    def test_future_payment_time_is_rejected(self):
        data = payment_data(self.order)
        data['occurred_at'] += timedelta(days=1)
        with self.assertRaises(BusinessError):
            record_payment(self.order.id, self.staff, data, uuid.uuid4())

    def test_expense_does_not_pay_order(self):
        record_payment(self.order.id, self.staff, payment_data(self.order, 500, kind='DIRECT_EXPENSE'), uuid.uuid4())
        self.assertEqual(money_summary(self.order)['state'], 'UNPAID')
