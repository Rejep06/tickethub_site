from datetime import timedelta
from unittest.mock import patch
from django.contrib import admin
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from core.email import notify
from core.models import EmailLog, ContentPage, ConsentRecord
from core.content import publish_page
from core.consents import accept_documents
from core.errors import BusinessError
from orders.models import Order, OrderItem
from tickets.models import TicketUnit
from payments.models import FinancialEntry
from tests.factories import manager, buyer, stock


class AdminSafetyTests(TestCase):
    def test_business_models_registered(self):
        for model in [Order, OrderItem, TicketUnit, FinancialEntry]:
            self.assertIn(model, admin.site._registry)

    def test_financial_admin_has_no_direct_add(self):
        from django.test import RequestFactory
        request = RequestFactory().get('/ops/')
        request.user = manager()
        request.session = {'_auth_user_backend': 'users.backends.StaffPasswordBackend'}
        model_admin = admin.site._registry[FinancialEntry]
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))

    def test_staff_otp_session_cannot_open_admin(self):
        self.client.force_login(manager(), backend='users.backends.CustomerOTPBackend')
        self.assertEqual(self.client.get('/ops/').status_code, 302)

    def test_manager_cannot_modify_order_state_directly(self):
        from tests.factories import order_fixture
        order, _ = order_fixture()
        self.client.force_login(manager(), backend='users.backends.StaffPasswordBackend')
        self.assertEqual(self.client.post(f'/ops/orders/order/{order.id}/change/', {'order_state': 'COMPLETED'}).status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.order_state, 'NEW')

    def test_idle_staff_session_expires(self):
        import time
        self.client.force_login(manager(), backend='users.backends.StaffPasswordBackend')
        session = self.client.session
        session['staff_started_at'] = int(time.time()) - 2000
        session['staff_seen_at'] = int(time.time()) - 1801
        session.save()
        self.assertEqual(self.client.get('/api/v1/staff/orders/').status_code, 401)

    def test_absolute_staff_session_expires(self):
        import time
        self.client.force_login(manager(), backend='users.backends.StaffPasswordBackend')
        session = self.client.session
        session['staff_started_at'] = int(time.time()) - 28801
        session['staff_seen_at'] = int(time.time())
        session.save()
        self.assertEqual(self.client.get('/api/v1/staff/orders/').status_code, 401)


class EmailAndConsentTests(TestCase):
    def test_business_mail_failure_does_not_rollback_saved_log(self):
        with patch('core.email.EmailMessage.send', side_effect=OSError('SMTP unavailable')):
            with self.captureOnCommitCallbacks(execute=True):
                row = notify('buyer@example.com', 'Subject', 'Business notice')
        row.refresh_from_db()
        self.assertEqual(row.status, 'FAILED')
        self.assertEqual(row.attempts, 1)

    @override_settings(REQUIRE_LEGAL_ACCEPTANCE=True)
    def test_missing_approved_legal_documents_blocks_order_acceptance(self):
        with self.assertRaises(BusinessError):
            accept_documents(buyer(), {}, 'ORDER')

    @override_settings(REQUIRE_LEGAL_ACCEPTANCE=True)
    def test_acceptance_records_actual_published_versions(self):
        actor = manager(role='ADMIN')
        user = buyer()
        for slug in ['privacy', 'offer', 'refund-policy']:
            page = ContentPage.objects.create(slug=slug, title_ru=slug, title_en=slug, body_ru='Test only', body_en='Test only')
            publish_page(page.id, actor)
        result = accept_documents(user, {'privacy': 1, 'offer': 1, 'refund-policy': 1}, 'ORDER')
        self.assertEqual(len(result), 3)
        self.assertEqual(ConsentRecord.objects.filter(user=user).count(), 3)


class InventoryMaintenanceTests(TestCase):
    def test_expired_supplier_allocation_can_be_explicitly_renewed(self):
        from tickets.services import renew_supplier_allocation
        _, _, units, _ = stock(1)
        unit = units[0]
        unit.stock_basis = 'EXCLUSIVE_ALLOCATION'
        unit.allocation_until = timezone.now() - timedelta(minutes=1)
        unit.status = 'BLOCKED'
        unit.save()
        result = renew_supplier_allocation(unit.id, manager(), unit.version, timezone.now() + timedelta(days=3), 'Supplier confirmed', True)
        self.assertEqual(result.status, 'BLOCKED')
        self.assertGreater(result.allocation_until, timezone.now())

    def test_missing_order_cost_can_be_corrected_with_audit(self):
        from tests.factories import confirmed_order
        from orders.services import update_item_cost
        from orders.serializers import OrderSerializer
        order, _, actor = confirmed_order(cost=None)
        item = order.items.get()
        result = update_item_cost(item.id, actor, order.version, 50000, 'Supplier invoice')
        item.refresh_from_db()
        self.assertEqual(item.purchase_price_minor, 50000)
        self.assertEqual(result.history.filter(event_type='COST_UPDATED').count(), 1)
        self.assertNotIn('COST_UPDATED', str(OrderSerializer(result).data))
