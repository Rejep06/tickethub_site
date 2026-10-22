import uuid
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from tests.factories import confirmed_order, payment_data, stock, buyer, manager, event_fixture
from payments.services import record_payment, approve_refund, record_refund
from orders.services import cancel_order, create_refund_request
from analytics.models import FunnelEvent
from analytics.services import dashboard, cashflow, funnel


class AnalyticsTests(TestCase):
    def test_order_created_is_server_fact(self):
        order, units, staff = confirmed_order()
        row = FunnelEvent.objects.get(order=order, event_type='ORDER_CREATED')
        self.assertEqual(row.source, 'SERVER')

    def test_cancelled_order_not_a_successful_sale(self):
        order, units, staff = confirmed_order()
        record_payment(order.id, staff, payment_data(order), uuid.uuid4())
        order.refresh_from_db()
        cancel_order(order.id, staff, order.version, 'Cancelled')
        report = dashboard({})
        self.assertEqual(report['successful_sales']['orders_count'], 0)
        self.assertEqual(report['successful_sales']['turnover_minor'], 0)
        self.assertEqual(report['paid_cohort_including_cancelled']['orders_count'], 1)

    def test_null_cost_does_not_become_zero_profit(self):
        order, units, staff = confirmed_order(cost=None)
        record_payment(order.id, staff, payment_data(order), uuid.uuid4())
        report = dashboard({})['successful_sales']
        self.assertIsNone(report['profit_minor'])
        self.assertFalse(report['profit_complete'])
        self.assertEqual(report['unknown_cost_count'], 1)

    def test_known_cost_profit(self):
        order, units, staff = confirmed_order(cost=60000)
        record_payment(order.id, staff, payment_data(order), uuid.uuid4())
        self.assertEqual(dashboard({})['successful_sales']['profit_minor'], 40000)

    def test_refund_in_cashflow(self):
        order, units, staff = confirmed_order()
        record_payment(order.id, staff, payment_data(order), uuid.uuid4())
        case, _ = create_refund_request(order.user, order.id, {'reason': 'Refund', 'kind': 'REFUND_REQUEST'})
        case = approve_refund(case.id, staff, case.version, 100000, 'Approved')
        order.refresh_from_db()
        record_refund(case.id, staff, {'expected_version': order.version, 'amount_minor': 100000,
            'occurred_at': timezone.now(), 'method': 'BANK_TRANSFER', 'reference': 'Actual refund'}, uuid.uuid4())
        report = cashflow({})
        self.assertEqual(report['customer_refunds_minor'], 100000)
        self.assertEqual(report['net_cashflow_minor'], 0)

    def test_order_funnel_conversions(self):
        order, units, staff = confirmed_order()
        rows = funnel({})['orders']
        self.assertEqual([r['count'] for r in rows], [1, 1, 1, 0, 0, 0])
        self.assertEqual(rows[2]['overall_conversion'], 1)
        self.assertEqual(rows[3]['conversion_from_previous'], 0)
        self.assertIsNone(rows[-1]['conversion_from_previous'])


@override_settings(CLIENT_ANALYTICS_ENABLED=True)
class AnalyticsAccessTests(APITestCase):
    def test_frontend_cannot_forge_payment(self):
        event = event_fixture()
        response = self.client.post('/api/v1/analytics/events/', {'event_id': str(event.id),
            'client_event_id': str(uuid.uuid4()), 'event_type': 'PAYMENT_RECEIVED', 'analytics_consent': True}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(FunnelEvent.objects.count(), 0)

    def test_client_event_requires_consent(self):
        event = event_fixture()
        response = self.client.post('/api/v1/analytics/events/', {'event_id': str(event.id),
            'client_event_id': str(uuid.uuid4()), 'event_type': 'EVENT_VIEW', 'analytics_consent': False}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_client_event_replay_does_not_count_twice(self):
        event = event_fixture()
        data = {'event_id': str(event.id), 'client_event_id': str(uuid.uuid4()), 'event_type': 'EVENT_VIEW', 'analytics_consent': True}
        self.assertEqual(self.client.post('/api/v1/analytics/events/', data, format='json').status_code, 201)
        self.assertEqual(self.client.post('/api/v1/analytics/events/', data, format='json').status_code, 200)
        self.assertEqual(FunnelEvent.objects.count(), 1)

    def test_customer_cannot_read_dashboard(self):
        self.client.force_login(buyer(), backend='users.backends.CustomerOTPBackend')
        self.assertEqual(self.client.get('/api/v1/staff/dashboard/summary/').status_code, 403)

    def test_manager_reads_dashboard(self):
        self.client.force_login(manager(), backend='users.backends.StaffPasswordBackend')
        self.assertEqual(self.client.get('/api/v1/staff/dashboard/summary/').status_code, 200)
