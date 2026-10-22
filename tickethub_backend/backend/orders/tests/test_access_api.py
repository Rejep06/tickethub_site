import uuid
from rest_framework.test import APITestCase
from tests.factories import buyer, manager, order_fixture, assert_no_private_fields
from orders.models import Order


class OrderAccessTests(APITestCase):
    def setUp(self):
        self.order, _ = order_fixture()
        self.other = buyer()

    def test_foreign_order_is_not_found(self):
        self.client.force_login(self.other, backend='users.backends.CustomerOTPBackend')
        response = self.client.get(f'/api/v1/orders/{self.order.id}/')
        self.assertEqual(response.status_code, 404)

    def test_order_list_only_contains_owned_orders(self):
        self.client.force_login(self.other, backend='users.backends.CustomerOTPBackend')
        response = self.client.get('/api/v1/orders/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)

    def test_own_order_is_safe(self):
        self.client.force_login(self.order.user, backend='users.backends.CustomerOTPBackend')
        response = self.client.get(f'/api/v1/orders/{self.order.id}/')
        self.assertEqual(response.status_code, 200)
        assert_no_private_fields(self, response.data)

    def test_customer_cannot_post_finance(self):
        self.client.force_login(self.order.user, backend='users.backends.CustomerOTPBackend')
        response = self.client.post(f'/api/v1/staff/orders/{self.order.id}/financial-entries/', {}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_direct_status_patch_forbidden_even_for_manager(self):
        self.client.force_login(manager(), backend='users.backends.StaffPasswordBackend')
        response = self.client.patch(f'/api/v1/staff/orders/{self.order.id}/', {'order_state': 'COMPLETED'}, format='json')
        self.assertEqual(response.status_code, 405)

    def test_manager_can_start_order_via_api(self):
        self.client.force_login(manager(), backend='users.backends.StaffPasswordBackend')
        response = self.client.post(f'/api/v1/staff/orders/{self.order.id}/start/', {'expected_version': self.order.version}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['order_state'], 'IN_PROGRESS')

    def test_order_requires_idempotency_header(self):
        self.client.force_login(self.order.user, backend='users.backends.CustomerOTPBackend')
        response = self.client.post('/api/v1/orders/', {'hold_id': str(self.order.hold_id)}, format='json')
        self.assertEqual(response.status_code, 400)
