import uuid
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.http import Http404
from core.errors import BusinessError
from tests.factories import buyer, manager, stock, assert_no_private_fields
from ticket_requests.models import TicketRequest, Quote
from ticket_requests.services import create_ticket_request, change_request, create_quote, send_quote, start_quote_checkout
from ticket_requests.serializers import RequestSerializer
from orders.services import create_order_from_hold
from tickets.models import CheckoutHold, TicketUnit


class RequestQuoteTests(TestCase):
    def setUp(self):
        self.user, self.staff = buyer(), manager()
        self.event, self.offer, self.units, self.selection = stock(2)

    def request_fixture(self, event=True):
        data = {'quantity': 2, 'accepted_documents': {}}
        if event:
            data['event_id'] = self.event.id
        else:
            data['custom_event_name'] = 'An event not in the catalogue'
        return create_ticket_request(self.user, data, uuid.uuid4())[0]

    def quote_fixture(self, request=None):
        request = request or self.request_fixture()
        quote = create_quote(request.id, self.staff, {'expected_version': request.version, 'event_id': self.event.id,
            'expires_at': timezone.now()+timedelta(days=1), 'items': [{'ticket_unit_id': u.id, 'price_minor': 110000} for u in self.units]})
        request.refresh_from_db()
        quote = send_quote(quote.id, self.staff, request.version)
        return request, quote

    def test_request_for_catalog_event(self):
        request = self.request_fixture()
        self.assertEqual(request.event_id, self.event.id)

    def test_request_without_event(self):
        request = self.request_fixture(False)
        self.assertIsNone(request.event_id)
        self.assertTrue(request.custom_event_name)

    def test_missing_event_description_rejected(self):
        with self.assertRaises(BusinessError):
            create_ticket_request(self.user, {'quantity': 1}, uuid.uuid4())

    def test_request_idempotency(self):
        data, key = {'quantity': 1, 'custom_event_name': 'Something'}, uuid.uuid4()
        first, _ = create_ticket_request(self.user, data, key)
        second, created = create_ticket_request(self.user, data, key)
        self.assertEqual(first.id, second.id)
        self.assertFalse(created)

    def test_manager_assignment(self):
        request = self.request_fixture()
        request = change_request(request.id, self.staff, {'expected_version': request.version, 'manager_id': self.staff.id})
        self.assertEqual(request.manager_id, self.staff.id)

    def test_quote_does_not_reserve_units(self):
        request, quote = self.quote_fixture()
        self.assertEqual(TicketUnit.objects.filter(status='AVAILABLE').count(), 2)
        self.assertEqual(CheckoutHold.objects.count(), 0)

    def test_quote_creates_hold(self):
        request, quote = self.quote_fixture()
        hold = start_quote_checkout(self.user, quote.id, quote.total_minor)
        self.assertEqual(hold.total_minor, 220000)
        self.assertEqual(hold.items.count(), 2)
        quote.refresh_from_db()
        self.assertEqual(quote.status, 'SENT')

    def test_quote_to_order_uses_common_flow(self):
        request, quote = self.quote_fixture()
        hold = start_quote_checkout(self.user, quote.id, quote.total_minor)
        order, _ = create_order_from_hold(self.user, {'hold_id': hold.id}, uuid.uuid4())
        self.assertEqual(order.origin, 'SITE_REQUEST')
        quote.refresh_from_db()
        request.refresh_from_db()
        self.assertEqual(quote.status, 'ACCEPTED')
        self.assertEqual(request.status, 'CONVERTED')

    def test_quote_cannot_convert_twice(self):
        request, quote = self.quote_fixture()
        hold = start_quote_checkout(self.user, quote.id, quote.total_minor)
        create_order_from_hold(self.user, {'hold_id': hold.id}, uuid.uuid4())
        with self.assertRaises(BusinessError):
            start_quote_checkout(self.user, quote.id, quote.total_minor)

    def test_expired_quote_rejected_without_cleanup(self):
        request, quote = self.quote_fixture()
        Quote.objects.filter(pk=quote.id).update(expires_at=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(BusinessError):
            start_quote_checkout(self.user, quote.id, quote.total_minor)

    def test_quote_stock_is_rechecked(self):
        request, quote = self.quote_fixture()
        TicketUnit.objects.filter(pk=self.units[0].id).update(status='BLOCKED')
        with self.assertRaises(BusinessError):
            start_quote_checkout(self.user, quote.id, quote.total_minor)

    def test_other_customer_cannot_use_quote(self):
        request, quote = self.quote_fixture()
        with self.assertRaises(Http404):
            start_quote_checkout(buyer(), quote.id, quote.total_minor)

    def test_draft_quote_is_not_in_public_response(self):
        request = self.request_fixture()
        create_quote(request.id, self.staff, {'expected_version': request.version, 'event_id': self.event.id,
            'expires_at': timezone.now()+timedelta(days=1), 'items': [{'ticket_unit_id': self.units[0].id, 'price_minor': 100000}]})
        self.assertEqual(RequestSerializer(request).data['quotes'], [])

    def test_customer_request_response_hides_internal_data(self):
        request, quote = self.quote_fixture()
        assert_no_private_fields(self, RequestSerializer(request).data)

    def test_required_adjacency_cannot_be_silently_dropped(self):
        request = self.request_fixture()
        request.together_required = True
        request.save()
        with self.assertRaises(BusinessError) as caught:
            create_quote(request.id, self.staff, {'expected_version': request.version, 'event_id': self.event.id,
                'expires_at': timezone.now()+timedelta(days=1), 'items': [{'ticket_unit_id': u.id, 'price_minor': 100000} for u in self.units]})
        self.assertEqual(caught.exception.business_code, 'ADJACENCY_NOT_CONFIRMED')

    def test_quote_supplies_price_when_public_offer_is_request_only(self):
        self.offer.mode = 'REQUEST'
        self.offer.sale_price_minor = None
        self.offer.save()
        from tickets.services import available_units
        self.assertEqual(available_units(self.event).count(), 0)
        request, quote = self.quote_fixture()
        hold = start_quote_checkout(self.user, quote.id, quote.total_minor)
        order, _ = create_order_from_hold(self.user, {'hold_id': hold.id}, uuid.uuid4())
        self.assertEqual(order.total_minor, 220000)
        self.assertEqual(order.discount_minor, 0)
        self.assertEqual(order.order_state, 'NEW')
