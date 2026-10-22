import uuid
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from core.errors import BusinessError
from tests.factories import buyer, stock
from tickets.models import CheckoutHold, TicketUnit
from tickets.services import create_hold, release_hold, cleanup_expired_holds, available_units, preview


class ReservationTests(TestCase):
    def setUp(self):
        self.user = buyer()
        self.event, self.offer, self.units, self.selection = stock(1, seated=True)

    def hold(self, user=None, **kwargs):
        return create_hold(user or self.user, self.event.id, self.selection, self.offer.sale_price_minor, **kwargs)

    def test_create_hold_for_exactly_ten_minutes(self):
        before = timezone.now()
        hold = self.hold()
        self.assertAlmostEqual((hold.expires_at-before).total_seconds(), 600, delta=3)
        self.units[0].refresh_from_db()
        self.assertEqual(self.units[0].status, 'CHECKOUT_HELD')
        self.assertEqual(self.units[0].current_hold_id, hold.id)

    def test_busy_seat_cannot_be_reserved(self):
        self.hold()
        with self.assertRaises(BusinessError) as caught:
            self.hold(buyer())
        self.assertEqual(caught.exception.business_code, 'SEAT_UNAVAILABLE')

    def test_refresh_does_not_extend_expiry(self):
        first = self.hold()
        second = self.hold()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.expires_at, second.expires_at)
        self.assertEqual(CheckoutHold.objects.count(), 1)

    def test_expired_hold_does_not_require_cron(self):
        old = self.hold()
        CheckoutHold.objects.filter(pk=old.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(available_units(self.event).count(), 1)
        new = self.hold(buyer())
        old.refresh_from_db()
        self.assertEqual(old.status, 'EXPIRED')
        self.assertNotEqual(old.pk, new.pk)

    def test_cleanup_only_expires_active_holds(self):
        hold = self.hold()
        CheckoutHold.objects.filter(pk=hold.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(cleanup_expired_holds(), 1)
        self.units[0].refresh_from_db()
        self.assertEqual(self.units[0].status, 'AVAILABLE')

    def test_release_is_repeatable(self):
        hold = self.hold()
        release_hold(self.user, hold.id)
        release_hold(self.user, hold.id)
        self.units[0].refresh_from_db()
        self.assertEqual(self.units[0].status, 'AVAILABLE')

    def test_other_customer_cannot_release(self):
        from django.http import Http404
        hold = self.hold()
        with self.assertRaises(Http404):
            release_hold(buyer(), hold.id)

    def test_preview_does_not_reserve(self):
        result = preview(self.event.id, self.selection)
        self.assertEqual(result['total_minor'], self.offer.sale_price_minor)
        self.assertEqual(CheckoutHold.objects.count(), 0)

    def test_price_change_rejected(self):
        with self.assertRaises(BusinessError) as caught:
            create_hold(self.user, self.event.id, self.selection, 1)
        self.assertEqual(caught.exception.business_code, 'PRICE_CHANGED')
        self.assertEqual(CheckoutHold.objects.count(), 0)

    def test_held_price_remains_fixed(self):
        hold = self.hold()
        self.offer.sale_price_minor += 5000
        self.offer.save()
        replay = self.hold()
        self.assertEqual(replay.total_minor, hold.total_minor)

    def test_partial_selection_is_not_reserved(self):
        selection = {'mode': 'SEATS', 'seat_ids': [self.units[0].seat_id, uuid.uuid4()]}
        with self.assertRaises(BusinessError):
            create_hold(self.user, self.event.id, selection, 200000)
        self.assertEqual(CheckoutHold.objects.count(), 0)

    def test_short_supplier_allocation_is_not_stock(self):
        unit = self.units[0]
        unit.stock_basis = 'EXCLUSIVE_ALLOCATION'
        unit.allocation_until = timezone.now()+timedelta(minutes=2)
        unit.save()
        self.assertEqual(available_units(self.event).count(), 0)

    def test_idempotency_replays_expired_hold_without_new_stock(self):
        key = uuid.uuid4()
        hold = self.hold(idempotency_key=key)
        CheckoutHold.objects.filter(pk=hold.id).update(expires_at=timezone.now()-timedelta(seconds=1))
        replay = self.hold(idempotency_key=key)
        self.assertEqual(replay.id, hold.id)
        self.assertEqual(CheckoutHold.objects.count(), 1)

    def test_idempotency_conflicting_body_fails(self):
        key = uuid.uuid4()
        self.hold(idempotency_key=key)
        with self.assertRaises(BusinessError) as caught:
            create_hold(self.user, self.event.id, self.selection, 999, idempotency_key=key)
        self.assertEqual(caught.exception.business_code, 'IDEMPOTENCY_CONFLICT')

    def test_category_reserves_real_units(self):
        event, offer, units, selection = stock(3)
        hold = create_hold(self.user, event.id, selection, 3*offer.sale_price_minor)
        self.assertEqual(hold.items.count(), 3)
        self.assertEqual(TicketUnit.objects.filter(current_hold=hold).count(), 3)

    def test_failed_replacement_keeps_original_hold(self):
        hold = self.hold()
        bad_selection = {'mode': 'SEATS', 'seat_ids': [uuid.uuid4()]}
        with self.assertRaises(BusinessError):
            create_hold(self.user, self.event.id, bad_selection, hold.total_minor)
        hold.refresh_from_db()
        self.units[0].refresh_from_db()
        self.assertEqual(hold.status, 'ACTIVE')
        self.assertEqual(self.units[0].current_hold_id, hold.id)
