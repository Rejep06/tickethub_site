import uuid
from django.test import TestCase
from django.utils import timezone
from core.errors import BusinessError
from tests.factories import confirmed_order, payment_data
from payments.services import record_payment, approve_refund, decide_case, record_refund
from payments.selectors import money_summary
from orders.services import create_refund_request, record_delivery


class RefundTests(TestCase):
    def setUp(self):
        self.order, self.units, self.staff = confirmed_order(2)
        record_payment(self.order.id, self.staff, payment_data(self.order), uuid.uuid4())
        self.items = list(self.order.items.all())

    def case(self, items=None):
        return create_refund_request(self.order.user, self.order.id, {'reason': 'Unable to attend',
            'item_ids': [item.id for item in (items or self.items)], 'kind': 'REFUND_REQUEST'})[0]

    def settle(self, case, amount):
        self.order.refresh_from_db()
        return record_refund(case.id, self.staff, {'expected_version': self.order.version, 'amount_minor': amount,
            'occurred_at': timezone.now(), 'method': 'BANK_TRANSFER', 'reference': 'Refund confirmation'}, uuid.uuid4())[0]

    def test_customer_creates_refund_case(self):
        case = self.case()
        self.assertEqual(case.status, 'NEW')

    def test_repeated_open_case_returns_same_case(self):
        self.assertEqual(self.case().id, self.case().id)

    def test_approval_does_not_transfer_money(self):
        case = self.case()
        approve_refund(case.id, self.staff, case.version, 200000, 'Approved')
        self.assertEqual(money_summary(self.order)['state'], 'PAID')
        self.assertEqual(money_summary(self.order)['refunded_minor'], 0)

    def test_manager_can_reject(self):
        case = self.case()
        case = decide_case(case.id, self.staff, case.version, 'REJECTED', 'Request declined')
        self.assertEqual(case.status, 'REJECTED')

    def test_actual_full_refund_is_recorded(self):
        case = self.case()
        case = approve_refund(case.id, self.staff, case.version, 200000, 'Approved')
        self.settle(case, 200000)
        self.assertEqual(money_summary(self.order)['state'], 'REFUNDED')
        case.refresh_from_db()
        self.assertEqual(case.status, 'CLOSED')

    def test_partial_refund(self):
        case = self.case(self.items[:1])
        case = approve_refund(case.id, self.staff, case.version, 100000, 'Approved for one ticket')
        self.settle(case, 100000)
        self.assertEqual(money_summary(self.order)['state'], 'PARTIALLY_REFUNDED')
        self.assertEqual(self.order.items.filter(is_active=True).count(), 1)

    def test_sent_ticket_is_blocked_after_refund(self):
        self.order.refresh_from_db()
        record_delivery(self.order.id, self.staff, {'expected_version': self.order.version, 'item_ids': [i.id for i in self.items],
            'recipient_email': self.order.customer_email, 'sent_at': timezone.now()}, uuid.uuid4())
        case = self.case()
        case = approve_refund(case.id, self.staff, case.version, 200000, 'Approved')
        self.settle(case, 200000)
        for unit in self.units:
            unit.refresh_from_db()
            self.assertEqual(unit.status, 'BLOCKED')

    def test_refund_without_approval_is_forbidden(self):
        with self.assertRaises(BusinessError):
            self.settle(self.case(), 1000)

    def test_refund_cannot_exceed_approved_amount(self):
        case = self.case()
        case = approve_refund(case.id, self.staff, case.version, 100000, 'Approved')
        with self.assertRaises(BusinessError):
            self.settle(case, 100001)

    def test_two_partial_transfers_settle_one_decision(self):
        case = self.case()
        case = approve_refund(case.id, self.staff, case.version, 200000, 'Approved')
        self.settle(case, 50000)
        case.refresh_from_db()
        self.assertEqual(case.status, 'APPROVED')
        self.settle(case, 150000)
        case.refresh_from_db()
        self.assertEqual(case.status, 'CLOSED')

    def test_approval_cannot_exceed_received(self):
        case = self.case()
        with self.assertRaises(BusinessError):
            approve_refund(case.id, self.staff, case.version, 200001, 'Too much')
