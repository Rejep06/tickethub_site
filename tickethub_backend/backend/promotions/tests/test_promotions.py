"""PostgreSQL/API tests: run with config.settings.test, not SQLite or mocks."""
import uuid
from datetime import timedelta
from types import SimpleNamespace
from django.test import TestCase, override_settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.http import Http404
from rest_framework.test import APIClient
from core.errors import BusinessError
from core.models import EmailLog
from core.public_api import public_configuration
from tests.factories import buyer, manager, stock, event_fixture, payment_data
from tickets.models import CheckoutHold, TicketUnit
from tickets.services import create_hold, available_units, cleanup_expired_holds
from orders.models import Order
from orders.services import create_order_from_hold, start_processing_order, confirm_order, cancel_order
from orders.serializers import OrderSerializer
from payments.services import record_payment
from payments.selectors import money_summary
from promotions.models import PromoCode, PromoRedemption
from promotions.services import preview_promotion, price_promotion, save_promotion


class PromoOrderTests(TestCase):
    def setUp(self):
        self.user = buyer()
        self.event, self.offer, self.units, self.selection = stock(3, price=100001)
        self.hold = create_hold(self.user, self.event.pk, self.selection, 300003)
        self.promo = save_promotion(None, {'code': 'MATCH10', 'kind': 'PERCENT', 'value': 10})

    def data(self, quote=None):
        quote = quote or preview_promotion(self.user, self.hold.pk, 'match10')
        return {'hold_id': self.hold.pk, 'accepted_documents': {}, 'promo_code': quote['code'],
                'expected_total_minor': quote['total_minor'], 'expected_discount_minor': quote['discount_minor'],
                'expected_promo_version': quote['promo_version']}

    def create(self, data=None, key=None):
        return create_order_from_hold(self.user, data or self.data(), key or uuid.uuid4())[0]

    def test_preview_case_normalization_does_not_consume(self):
        result = preview_promotion(self.user, self.hold.pk, ' match10 ')
        self.assertEqual(result['code'], 'MATCH10')
        self.assertEqual(result['discount_minor'], 30000)
        self.assertEqual(result['total_minor'], 270003)
        self.assertFalse(PromoRedemption.objects.exists())

    def test_foreign_hold_is_not_disclosed(self):
        with self.assertRaises(Http404):
            preview_promotion(buyer(), self.hold.pk, 'MATCH10')

    def test_order_has_exact_net_snapshots(self):
        order = self.create()
        self.assertEqual((order.order_state, order.total_minor, order.discount_minor), ('NEW', 270003, 30000))
        self.assertEqual(sum(order.items.values_list('original_price_minor', flat=True)), order.subtotal_minor)
        self.assertEqual(sum(order.items.values_list('discount_minor', flat=True)), order.discount_minor)
        self.assertEqual(sum(order.items.values_list('sale_price_minor', flat=True)), order.total_minor)
        self.assertEqual(PromoRedemption.objects.get().order_id, order.pk)
        self.assertTrue(all(u.status == 'ORDER_HELD' for u in TicketUnit.objects.filter(pk__in=[x.pk for x in self.units])))

    def test_plain_checkout_preserves_gross_price(self):
        order = self.create({'hold_id': self.hold.pk, 'accepted_documents': {}})
        self.assertEqual(order.total_minor, 300003)
        self.assertEqual(order.subtotal_minor, order.total_minor)
        self.assertEqual(order.discount_minor, 0)
        self.assertEqual(order.promo_code, '')
        self.assertFalse(PromoRedemption.objects.exists())

    def test_replay_after_disable_returns_original_once(self):
        data, key = self.data(), uuid.uuid4()
        first = self.create(data, key)
        save_promotion(self.promo, {'expected_version': 1, 'is_active': False})
        repeat, created = create_order_from_hold(self.user, data, key)
        self.assertEqual(repeat.pk, first.pk)
        self.assertFalse(created)
        self.assertEqual(PromoRedemption.objects.count(), 1)
        self.assertEqual(Order.objects.count(), 1)

    def test_changed_payload_same_key_is_conflict(self):
        data, key = self.data(), uuid.uuid4()
        self.create(data, key)
        with self.assertRaises(BusinessError) as exc:
            self.create({**data, 'expected_total_minor': 1}, key)
        self.assertEqual(exc.exception.business_code, 'IDEMPOTENCY_CONFLICT')

    def test_forged_total_rolls_back_order_and_usage(self):
        data = {**self.data(), 'expected_total_minor': 1}
        with self.assertRaises(BusinessError) as exc:
            self.create(data)
        self.assertEqual(exc.exception.business_code, 'PROMO_CHANGED')
        self.assertFalse(Order.objects.exists())
        self.assertFalse(PromoRedemption.objects.exists())
        self.hold.refresh_from_db()
        self.assertEqual(self.hold.status, 'ACTIVE')

    def test_edited_code_requires_new_customer_confirmation(self):
        data = self.data()
        save_promotion(self.promo, {'expected_version': 1, 'value': 15})
        with self.assertRaises(BusinessError) as exc:
            self.create(data)
        self.assertEqual(exc.exception.business_code, 'PROMO_CHANGED')
        quote = preview_promotion(self.user, self.hold.pk, 'MATCH10')
        self.assertEqual(self.create(self.data(quote)).discount_minor, 45000)

    def test_expired_promo_is_checked_again_at_order_submission(self):
        data = self.data()
        PromoCode.objects.filter(pk=self.promo.pk).update(ends_at=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(BusinessError) as exc:
            self.create(data)
        self.assertEqual(exc.exception.business_code, 'PROMO_EXPIRED')
        self.assertFalse(Order.objects.exists())

    def test_expired_hold_cannot_use_promo(self):
        CheckoutHold.objects.filter(pk=self.hold.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(BusinessError) as exc:
            preview_promotion(self.user, self.hold.pk, 'MATCH10')
        self.assertEqual(exc.exception.business_code, 'HOLD_EXPIRED')

    def test_not_started(self):
        PromoCode.objects.filter(pk=self.promo.pk).update(starts_at=timezone.now()+timedelta(days=1))
        with self.assertRaises(BusinessError) as exc:
            preview_promotion(self.user, self.hold.pk, 'MATCH10')
        self.assertEqual(exc.exception.business_code, 'PROMO_NOT_STARTED')

    def test_event_scope(self):
        PromoCode.objects.filter(pk=self.promo.pk).update(event=event_fixture())
        with self.assertRaises(BusinessError) as exc:
            preview_promotion(self.user, self.hold.pk, 'MATCH10')
        self.assertEqual(exc.exception.business_code, 'PROMO_EVENT')

    def test_minimum_and_cap(self):
        save_promotion(self.promo, {'expected_version': 1, 'minimum_total_minor': 300004})
        with self.assertRaises(BusinessError) as exc:
            preview_promotion(self.user, self.hold.pk, 'MATCH10')
        self.assertEqual(exc.exception.business_code, 'PROMO_MINIMUM')
        self.promo.refresh_from_db()
        save_promotion(self.promo, {'expected_version': 2, 'minimum_total_minor': 300003, 'maximum_discount_minor': 1234})
        self.assertEqual(preview_promotion(self.user, self.hold.pk, 'MATCH10')['discount_minor'], 1234)

    def test_fixed_and_allocation_remainder(self):
        save_promotion(self.promo, {'expected_version': 1, 'kind': 'FIXED', 'value': 10000})
        order = self.create()
        discounts = list(order.items.order_by('ticket_unit_id').values_list('discount_minor', flat=True))
        self.assertEqual(discounts, [3334, 3333, 3333])

    def test_personal_quote_cannot_stack(self):
        # This branch is intentionally independent of Quote setup: it rejects before reading a promo.
        with self.assertRaises(BusinessError) as exc:
            price_promotion(self.user, SimpleNamespace(quote_id=uuid.uuid4()), 'MATCH10')
        self.assertEqual(exc.exception.business_code, 'PROMO_QUOTE')

    def test_cancel_does_not_restore_quota(self):
        PromoCode.objects.filter(pk=self.promo.pk).update(usage_limit=1)
        order = self.create()
        cancel_order(order.pk, manager(), order.version, 'Customer cancelled', True)
        other = buyer()
        hold = create_hold(other, self.event.pk, self.selection, 300003)
        with self.assertRaises(BusinessError) as exc:
            preview_promotion(other, hold.pk, 'MATCH10')
        self.assertEqual(exc.exception.business_code, 'PROMO_LIMIT')
        self.assertEqual(PromoRedemption.objects.count(), 1)

    def test_per_user_limit_is_cross_event(self):
        self.create()
        event, offer, _, selection = stock()
        hold = create_hold(self.user, event.pk, selection, offer.sale_price_minor)
        with self.assertRaises(BusinessError) as exc:
            preview_promotion(self.user, hold.pk, 'MATCH10')
        self.assertEqual(exc.exception.business_code, 'PROMO_USER_LIMIT')

    def test_new_user_can_use_after_other_customer(self):
        self.create()
        other = buyer()
        event, offer, _, selection = stock()
        hold = create_hold(other, event.pk, selection, offer.sale_price_minor)
        self.assertGreater(preview_promotion(other, hold.pk, 'MATCH10')['discount_minor'], 0)

    def test_existing_order_is_immutable_when_promo_changes(self):
        order = self.create()
        save_promotion(self.promo, {'expected_version': 1, 'value': 30, 'is_active': False})
        order.refresh_from_db()
        data = OrderSerializer(order).data
        self.assertEqual((data['promo_code'], data['discount_minor'], data['total_minor']), ('MATCH10', 30000, 270003))

    def test_discount_is_used_for_payment_and_units_after_confirmation(self):
        order, actor = self.create(), manager()
        order = start_processing_order(order.pk, actor, order.version)
        order = confirm_order(order.pk, actor, order.version)
        record_payment(order.pk, actor, payment_data(order), uuid.uuid4())
        self.assertEqual(money_summary(order)['state'], 'PAID')
        self.assertEqual(money_summary(order)['received_minor'], 270003)
        self.assertEqual(TicketUnit.objects.filter(status='SOLD').count(), 3)

    def test_discounted_order_cannot_be_paid_gross_amount(self):
        order = self.create()
        with self.assertRaises(BusinessError) as exc:
            record_payment(order.pk, manager(), payment_data(order, amount=300003), uuid.uuid4())
        self.assertEqual(exc.exception.business_code, 'OVERPAYMENT')

    def test_checkout_expiry_never_releases_submitted_order(self):
        order = self.create()
        CheckoutHold.objects.filter(pk=self.hold.pk).update(expires_at=timezone.now()-timedelta(hours=1))
        cleanup_expired_holds()
        self.assertEqual(TicketUnit.objects.filter(status='ORDER_HELD').count(), 3)
        self.assertEqual(order.items.filter(is_active=True).count(), 3)

    @override_settings(STAFF_NOTIFICATION_EMAILS=['manager@example.test'], SITE_URL='https://tickethub.example')
    def test_manager_notice_has_actual_amount_and_order_link(self):
        order = self.create()
        notice = EmailLog.objects.get(recipient='manager@example.test')
        self.assertIn(f'/ru/staff/orders/{order.pk}', notice.body)
        self.assertIn('MATCH10', notice.body)
        self.assertIn('2 700.03', notice.body)


class PromoAPITests(TestCase):
    def setUp(self):
        self.user, self.admin, self.manager = buyer(), manager(role='ADMIN'), manager()
        self.client = APIClient()
        self.event, self.offer, self.units, self.selection = stock()
        self.hold = create_hold(self.user, self.event.pk, self.selection, self.offer.sale_price_minor)
        self.promo = save_promotion(None, {'code': 'MATCH10', 'kind': 'PERCENT', 'value': 10})

    def login(self, user, staff=False):
        self.client.force_login(user, backend='users.backends.StaffPasswordBackend' if staff else 'users.backends.CustomerOTPBackend')

    def test_preview_auth_required(self):
        response = self.client.post('/api/v1/checkout/promo/', {'hold_id': str(self.hold.pk), 'code': 'MATCH10'}, format='json')
        self.assertIn(response.status_code, [401, 403])

    def test_customer_preview_and_order_api(self):
        self.login(self.user)
        preview = self.client.post('/api/v1/checkout/promo/', {'hold_id': str(self.hold.pk), 'code': 'MATCH10'}, format='json')
        self.assertEqual(preview.status_code, 200, preview.data)
        quote = preview.data
        data = {'hold_id': str(self.hold.pk), 'promo_code': quote['code'], 'expected_promo_version': quote['promo_version'],
                'expected_discount_minor': quote['discount_minor'], 'expected_total_minor': quote['total_minor']}
        response = self.client.post('/api/v1/orders/', data, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['order_state'], 'NEW')
        hold = self.client.get(f'/api/v1/checkout/holds/{self.hold.pk}/')
        self.assertEqual(str(hold.data['order_id']), str(response.data['id']))
        self.login(self.manager, True)
        queue = self.client.get('/api/v1/staff/orders/?state=NEW')
        self.assertEqual(str(queue.data['results'][0]['id']), str(response.data['id']))

    def test_customer_cannot_enumerate_codes(self):
        self.login(self.user)
        self.assertEqual(self.client.get('/api/v1/staff/promo-codes/').status_code, 403)

    def test_staff_email_with_customer_session_is_not_admin(self):
        self.login(self.admin, False)
        self.assertEqual(self.client.get('/api/v1/staff/promo-codes/').status_code, 403)

    def test_manager_read_only(self):
        self.login(self.manager, True)
        self.assertEqual(self.client.get('/api/v1/staff/promo-codes/').status_code, 200)
        response = self.client.patch(f'/api/v1/staff/promo-codes/{self.promo.pk}/', {'is_active': False, 'expected_version': 1}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_admin_create_edit_and_no_delete(self):
        self.login(self.admin, True)
        response = self.client.post('/api/v1/staff/promo-codes/', {'code': ' day500 ', 'kind': 'FIXED', 'value': 50000}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['code'], 'DAY500')
        url = f'/api/v1/staff/promo-codes/{response.data["id"]}/'
        self.assertEqual(self.client.patch(url, {'expected_version': 1, 'is_active': False}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(url, {'expected_version': 1, 'is_active': True}, format='json').status_code, 409)
        self.assertEqual(self.client.delete(url).status_code, 405)

    def test_total_override_and_unapplied_code_rejected(self):
        self.login(self.user)
        for extra in [{'total_minor': 1}, {'promo_code': 'MATCH10'}, {'expected_discount_minor': 100}]:
            response = self.client.post('/api/v1/orders/', {'hold_id': str(self.hold.pk), **extra}, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
            self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Order.objects.exists())

    def test_csrf_is_still_required(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user, backend='users.backends.CustomerOTPBackend')
        response = client.post('/api/v1/checkout/promo/', {'hold_id': str(self.hold.pk), 'code': 'MATCH10'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_foreign_hold_preview_returns_404(self):
        self.login(buyer())
        response = self.client.post('/api/v1/checkout/promo/', {'hold_id': str(self.hold.pk), 'code': 'MATCH10'}, format='json')
        self.assertEqual(response.status_code, 404)

    def test_code_rename_and_hundred_percent_are_invalid(self):
        with self.assertRaises(ValidationError):
            save_promotion(self.promo, {'expected_version': 1, 'code': 'RENAMED'})
        with self.assertRaises(ValidationError):
            save_promotion(self.promo, {'expected_version': 1, 'value': 100})


class ManualIntakeTests(TestCase):
    def test_metadata_and_old_delivery_sla_do_not_block_available_stock(self):
        event = event_fixture(start_at=timezone.now()+timedelta(hours=2), sale_deadline=None,
                              refund_policy_approved=False, refund_policy_ru='', refund_policy_en='', fan_id_required=None)
        event, offer, units, selection = stock(event=event)
        user = buyer()
        hold = create_hold(user, event.pk, selection, offer.sale_price_minor)
        order, _ = create_order_from_hold(user, {'hold_id': hold.pk}, uuid.uuid4())
        self.assertEqual(order.order_state, 'NEW')
        self.assertIsNone(order.delivery_due_at)

    def test_real_stock_is_orderable_despite_legacy_request_mode(self):
        event, offer, units, selection = stock()
        offer.mode = 'REQUEST'
        offer.save()
        self.assertEqual(available_units(event).count(), 1)
        hold = create_hold(buyer(), event.pk, selection, offer.sale_price_minor)
        self.assertEqual(hold.items.count(), 1)

    def test_request_without_stock_never_invents_tickets(self):
        event, offer, units, selection = stock()
        TicketUnit.objects.filter(pk=units[0].pk).update(status='BLOCKED')
        self.assertEqual(available_units(event).count(), 0)
        with self.assertRaises(BusinessError):
            create_hold(buyer(), event.pk, selection, offer.sale_price_minor)

    def test_online_payment_mode_is_not_intake_switch(self):
        config = public_configuration()
        self.assertTrue(config['order_intake_enabled'])
        self.assertFalse(config['online_payments_enabled'])
        self.assertEqual(config['checkout_mode'], 'MANAGER')

    @override_settings(ORDER_INTAKE_ENABLED=False)
    def test_intentional_maintenance_switch_remains(self):
        event, offer, _, selection = stock()
        with self.assertRaises(BusinessError) as exc:
            create_hold(buyer(), event.pk, selection, offer.sale_price_minor)
        self.assertEqual(exc.exception.business_code, 'FORMS_DISABLED')

    def test_postponed_date_tba_orders_are_manager_review_not_fake_date(self):
        event = event_fixture(status='POSTPONED', date_tba=True, start_at=None, sale_deadline=None)
        event, offer, _, selection = stock(event=event)
        user = buyer()
        hold = create_hold(user, event.pk, selection, offer.sale_price_minor)
        order, _ = create_order_from_hold(user, {'hold_id': hold.pk}, uuid.uuid4())
        self.assertIsNone(order.event_snapshot['start_at'])
        self.assertIsNone(order.delivery_due_at)
