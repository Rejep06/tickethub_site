import uuid
from django.test import TestCase
from django.utils import timezone
from core.errors import BusinessError
from tests.factories import confirmed_order, payment_data
from payments.services import record_payment
from payments.selectors import sent_summary
from orders.services import record_delivery, complete_order, void_delivery


class DeliveryTests(TestCase):
    def setUp(self):
        self.order, self.units, self.staff = confirmed_order(4)
        record_payment(self.order.id, self.staff, payment_data(self.order), uuid.uuid4())
        self.items = list(self.order.items.all())

    def send(self, items, key=None):
        self.order.refresh_from_db()
        return record_delivery(self.order.id, self.staff, {'expected_version': self.order.version,
            'item_ids': [item.id for item in items], 'recipient_email': self.order.customer_email, 'sent_at': timezone.now()}, key or uuid.uuid4())[0]

    def test_no_delivery(self):
        self.assertEqual(sent_summary(self.order), {'state': 'NOT_SENT', 'sent_count': 0, 'active_count': 4})

    def test_two_of_four_is_partial(self):
        self.send(self.items[:2])
        self.assertEqual(sent_summary(self.order)['state'], 'PARTIALLY_SENT')
        self.assertEqual(sent_summary(self.order)['sent_count'], 2)

    def test_resend_does_not_inflate_count(self):
        self.send(self.items[:2])
        self.send(self.items[:2])
        self.assertEqual(sent_summary(self.order)['sent_count'], 2)
        self.assertEqual(sent_summary(self.order)['state'], 'PARTIALLY_SENT')

    def test_four_of_four_is_sent(self):
        self.send(self.items[:2])
        self.send(self.items[2:])
        self.assertEqual(sent_summary(self.order)['state'], 'SENT')

    def test_fully_delivered_order_can_complete(self):
        self.send(self.items)
        self.order.refresh_from_db()
        result = complete_order(self.order.id, self.staff, self.order.version)
        self.assertEqual(result.order_state, 'COMPLETED')

    def test_partial_delivery_cannot_complete(self):
        self.send(self.items[:2])
        self.order.refresh_from_db()
        with self.assertRaises(BusinessError):
            complete_order(self.order.id, self.staff, self.order.version)

    def test_void_corrects_delivery_count(self):
        record = self.send(self.items)
        self.order.refresh_from_db()
        void_delivery(record.id, self.staff, self.order.version, 'Wrong selection')
        self.assertEqual(sent_summary(self.order)['state'], 'NOT_SENT')

    def test_foreign_item_is_rejected(self):
        self.order.refresh_from_db()
        with self.assertRaises(BusinessError):
            record_delivery(self.order.id, self.staff, {'expected_version': self.order.version,
                'item_ids': [uuid.uuid4()], 'recipient_email': self.order.customer_email, 'sent_at': timezone.now()}, uuid.uuid4())

    def test_unverified_recipient_email_is_rejected(self):
        self.order.refresh_from_db()
        with self.assertRaises(BusinessError):
            record_delivery(self.order.id, self.staff, {'expected_version': self.order.version,
                'item_ids': [self.items[0].id], 'recipient_email': 'other@example.com', 'sent_at': timezone.now()}, uuid.uuid4())
