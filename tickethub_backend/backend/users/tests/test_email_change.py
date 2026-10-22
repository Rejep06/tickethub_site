import re
from datetime import timedelta
from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient
from tests.factories import buyer
from users.models import User


class EmailChangeTests(TestCase):
    def setUp(self):
        self.user = buyer('old@example.com')
        self.client = APIClient()
        self.client.force_login(self.user, backend='users.backends.CustomerOTPBackend')

    def start(self):
        response = self.client.post('/api/v1/me/email-change/start/', {'new_email': 'new@example.com'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return [re.search(r'\b([0-9]{6})\b', message.body).group(1) for message in mail.outbox[-2:]]

    def test_both_addresses_must_be_confirmed(self):
        old, new = self.start()
        response = self.client.post('/api/v1/me/email-change/confirm/', {'old_code': old, 'new_code': new}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['email'], 'new@example.com')
        self.assertFalse(User.objects.filter(email='old@example.com').exists())

    def test_wrong_code_does_not_change_email(self):
        old, new = self.start()
        wrong = '000000' if new != '000000' else '000001'
        response = self.client.post('/api/v1/me/email-change/confirm/', {'old_code': old, 'new_code': wrong}, format='json')
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'old@example.com')

    def test_other_sessions_are_revoked(self):
        other = APIClient()
        other.force_login(self.user, backend='users.backends.CustomerOTPBackend')
        old, new = self.start()
        response = self.client.post('/api/v1/me/email-change/confirm/', {'old_code': old, 'new_code': new}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(other.get('/api/v1/me/').status_code, 401)
        self.assertEqual(self.client.get('/api/v1/me/').status_code, 200)

    def test_codes_are_not_reusable(self):
        old, new = self.start()
        body = {'old_code': old, 'new_code': new}
        self.assertEqual(self.client.post('/api/v1/me/email-change/confirm/', body, format='json').status_code, 200)
        self.assertEqual(self.client.post('/api/v1/me/email-change/confirm/', body, format='json').status_code, 400)

    def test_existing_orders_keep_email_snapshot(self):
        from tests.factories import order_fixture
        order, _ = order_fixture(user=self.user)
        old, new = self.start()
        self.assertEqual(self.client.post('/api/v1/me/email-change/confirm/', {'old_code': old, 'new_code': new}, format='json').status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.customer_email, 'old@example.com')
