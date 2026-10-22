import uuid
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.http import Http404
from core.errors import BusinessError
from tests.factories import buyer, stock, order_fixture, manager, assert_no_private_fields
from tickets.models import CheckoutHold, TicketUnit
from tickets.services import create_hold, cleanup_expired_holds
from orders.models import Order, OrderItem
from orders.services import create_order_from_hold, cancel_order, complete_order, start_processing_order, confirm_order
from orders.serializers import OrderSerializer


class OrderTests(TestCase):
    def setUp(self):
        self.user = buyer()
        self.event, self.offer, self.units, self.selection = stock(1)
        self.hold = create_hold(self.user, self.event.id, self.selection, self.offer.sale_price_minor)
        self.data = {'hold_id': self.hold.id, 'accepted_documents': {}}
        self.staff = manager()

    def create(self, key=None):
        return create_order_from_hold(self.user, self.data, key or uuid.uuid4())[0]

    def test_order_from_valid_hold(self):
        order = self.create()
        self.assertEqual(order.order_state, 'NEW')
        self.assertEqual(order.total_minor, self.hold.total_minor)
        self.assertEqual(order.items.count(), 1)

    def test_expired_hold_rejected(self):
        CheckoutHold.objects.filter(pk=self.hold.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(BusinessError):
            self.create()
        self.assertEqual(Order.objects.count(), 0)

    def test_foreign_hold_is_404(self):
        with self.assertRaises(Http404):
            create_order_from_hold(buyer(), self.data, uuid.uuid4())

    def test_hold_cannot_make_two_orders(self):
        self.create()
        with self.assertRaises(BusinessError):
            self.create()
        self.assertEqual(Order.objects.count(), 1)

    def test_idempotency_returns_same_order(self):
        key = uuid.uuid4()
        first = self.create(key)
        second, created = create_order_from_hold(self.user, self.data, key)
        self.assertEqual(first.id, second.id)
        self.assertFalse(created)

    def test_idempotency_conflicting_payload_fails(self):
        key = uuid.uuid4()
        self.create(key)
        with self.assertRaises(BusinessError) as caught:
            create_order_from_hold(self.user, {**self.data, 'comment': 'different'}, key)
        self.assertEqual(caught.exception.business_code, 'IDEMPOTENCY_CONFLICT')

    def test_snapshot_does_not_change(self):
        order = self.create()
        price = order.items.get().sale_price_minor
        title = order.event_snapshot['title_ru']
        self.offer.name_ru = 'Changed'
        self.offer.sale_price_minor += 100
        self.offer.save()
        self.event.title_ru = 'Changed event'
        self.event.save()
        order.refresh_from_db()
        self.assertEqual(order.items.get().sale_price_minor, price)
        self.assertEqual(order.event_snapshot['title_ru'], title)

    def test_order_detaches_checkout_timer(self):
        order = self.create()
        CheckoutHold.objects.filter(pk=self.hold.id).update(expires_at=timezone.now()-timedelta(hours=1))
        cleanup_expired_holds()
        self.units[0].refresh_from_db()
        self.assertEqual(self.units[0].status, 'ORDER_HELD')
        self.assertIsNone(self.units[0].current_hold_id)
        self.assertTrue(order.items.get().is_active)

    def test_cannot_buy_order_held_ticket(self):
        self.create()
        with self.assertRaises(BusinessError):
            create_hold(buyer(), self.event.id, self.selection, self.offer.sale_price_minor)

    def test_cancel_unpaid_releases_unit(self):
        order = self.create()
        cancel_order(order.id, self.staff, order.version, 'Customer cancelled', True)
        self.units[0].refresh_from_db()
        self.assertEqual(self.units[0].status, 'AVAILABLE')
        self.assertFalse(order.items.get().is_active)

    def test_cancel_requires_no_pending_settlements_confirmation(self):
        order = self.create()
        with self.assertRaises(BusinessError):
            cancel_order(order.id, self.staff, order.version, 'Reason')
        self.units[0].refresh_from_db()
        self.assertEqual(self.units[0].status, 'ORDER_HELD')

    def test_old_version_rejected(self):
        order = self.create()
        with self.assertRaises(BusinessError) as caught:
            start_processing_order(order.id, self.staff, order.version+1)
        self.assertEqual(caught.exception.business_code, 'VERSION_CONFLICT')

    def test_manager_workflow(self):
        order = self.create()
        order = start_processing_order(order.id, self.staff, order.version)
        order = confirm_order(order.id, self.staff, order.version)
        self.assertEqual(order.order_state, 'CONFIRMED')

    def test_incomplete_order_cannot_complete(self):
        order = self.create()
        with self.assertRaises(BusinessError):
            complete_order(order.id, self.staff, order.version)

    def test_required_profile(self):
        self.user.phone = ''
        self.user.save()
        with self.assertRaises(BusinessError) as caught:
            self.create()
        self.assertEqual(caught.exception.business_code, 'PROFILE_INCOMPLETE')

    def test_fan_id_acknowledgement_required(self):
        self.event.fan_id_required = True
        self.event.save()
        with self.assertRaises(BusinessError) as caught:
            self.create()
        self.assertEqual(caught.exception.business_code, 'FAN_ID_ACK_REQUIRED')
        self.data['fan_id_answer'] = 'NEEDS_HELP'
        order = self.create()
        self.assertEqual(order.fan_id_help_state, 'REQUESTED')

    def test_customer_serializer_has_no_internal_data(self):
        order = self.create()
        assert_no_private_fields(self, OrderSerializer(order).data)

    def test_price_cannot_be_overridden_in_order_input(self):
        from orders.serializers import CreateOrderSerializer
        serializer = CreateOrderSerializer(data={'hold_id': str(self.hold.id), 'total_minor': 1, 'passport_number': 'xxx'})
        self.assertFalse(serializer.is_valid())
