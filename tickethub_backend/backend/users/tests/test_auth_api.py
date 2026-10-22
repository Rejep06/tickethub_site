import re
from datetime import timedelta
from unittest.mock import patch
from django.conf import settings
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from users.models import AuthChallenge, User
from users import services
from tests.factories import buyer, manager, PASSWORD


class OTPTests(APITestCase):
    def send_code(self, email='buyer@example.com'):
        response = self.client.post('/api/v1/auth/otp/request/', {'email': email}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return re.search(r'(?<![0-9])[0-9]{6}(?![0-9])', mail.outbox[-1].body).group()

    def test_request_sends_code_not_plain_database_value(self):
        code = self.send_code()
        challenge = AuthChallenge.objects.get(email='buyer@example.com')
        self.assertNotEqual(challenge.code_hmac, code)
        self.assertEqual(len(challenge.code_hmac), 64)
        self.assertEqual((challenge.expires_at-challenge.issued_at).total_seconds(), 600)

    def test_verify_registers_and_logs_in(self):
        code = self.send_code()
        response = self.client.post('/api/v1/auth/otp/verify/', {'email': 'buyer@example.com', 'code': code}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(User.objects.get(email='buyer@example.com').email_verified_at)
        self.assertEqual(self.client.get('/api/v1/me/').status_code, 200)

    def test_wrong_code_counts_attempt(self):
        self.send_code()
        response = self.client.post('/api/v1/auth/otp/verify/', {'email': 'buyer@example.com', 'code': 'not-code'}, format='json')
        self.assertEqual(response.status_code, 400)
        with patch('users.services.secrets.randbelow', return_value=123456):
            AuthChallenge.objects.update(issued_at=timezone.now()-timedelta(minutes=2))
            services.request_code('buyer@example.com', '127.0.0.1')
        response = self.client.post('/api/v1/auth/otp/verify/', {'email': 'buyer@example.com', 'code': '000000'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(AuthChallenge.objects.get(email='buyer@example.com').attempts, 1)

    def test_expired_code_fails(self):
        code = self.send_code()
        AuthChallenge.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
        response = self.client.post('/api/v1/auth/otp/verify/', {'email': 'buyer@example.com', 'code': code}, format='json')
        self.assertEqual(response.data['code'], 'OTP_EXPIRED')

    def test_code_is_single_use(self):
        code = self.send_code()
        body = {'email': 'buyer@example.com', 'code': code}
        self.assertEqual(self.client.post('/api/v1/auth/otp/verify/', body, format='json').status_code, 200)
        self.assertEqual(self.client.post('/api/v1/auth/otp/verify/', body, format='json').status_code, 400)

    def test_five_wrong_attempts_disable_correct_code(self):
        code = self.send_code()
        wrong = '000000' if code != '000000' else '111111'
        for _ in range(5):
            self.client.post('/api/v1/auth/otp/verify/', {'email': 'buyer@example.com', 'code': wrong}, format='json')
        self.assertEqual(self.client.post('/api/v1/auth/otp/verify/', {'email': 'buyer@example.com', 'code': code}, format='json').status_code, 400)

    def test_resend_cooldown(self):
        self.send_code()
        self.assertEqual(self.client.post('/api/v1/auth/otp/request/', {'email': 'buyer@example.com'}, format='json').status_code, 429)

    def test_hourly_limit_survives_new_challenge(self):
        for _ in range(5):
            AuthChallenge.objects.update(issued_at=timezone.now()-timedelta(minutes=2))
            self.assertEqual(self.client.post('/api/v1/auth/otp/request/', {'email': 'buyer@example.com'}, format='json').status_code, 200)
        AuthChallenge.objects.update(issued_at=timezone.now()-timedelta(minutes=2))
        self.assertEqual(self.client.post('/api/v1/auth/otp/request/', {'email': 'buyer@example.com'}, format='json').status_code, 429)

    def test_new_code_invalidates_old(self):
        with patch('users.services.secrets.randbelow', return_value=123456):
            self.send_code()
        AuthChallenge.objects.update(issued_at=timezone.now()-timedelta(minutes=2))
        with patch('users.services.secrets.randbelow', return_value=654321):
            self.send_code()
        result = self.client.post('/api/v1/auth/otp/verify/', {'email': 'buyer@example.com', 'code': '123456'}, format='json')
        self.assertEqual(result.status_code, 400)

    @override_settings(PUBLIC_FORMS_ENABLED=False)
    def test_existing_customer_can_login_when_forms_closed(self):
        buyer('buyer@example.com')
        code = self.send_code()
        result = self.client.post('/api/v1/auth/otp/verify/', {'email': 'buyer@example.com', 'code': code}, format='json')
        self.assertEqual(result.status_code, 200)

    @override_settings(PUBLIC_FORMS_ENABLED=False)
    def test_new_registration_is_disabled_when_forms_closed(self):
        code = self.send_code()
        result = self.client.post('/api/v1/auth/otp/verify/', {'email': 'buyer@example.com', 'code': code}, format='json')
        self.assertEqual(result.status_code, 409)
        self.assertFalse(User.objects.filter(email='buyer@example.com').exists())

    def test_email_failure_invalidates_code(self):
        with patch('users.services.send_mail', side_effect=RuntimeError('SMTP offline')):
            response = self.client.post('/api/v1/auth/otp/request/', {'email': 'buyer@example.com'}, format='json')
        self.assertEqual(response.status_code, 503)
        self.assertIsNotNone(AuthChallenge.objects.get(email='buyer@example.com').consumed_at)

    def test_profile_changes_name_and_international_phone(self):
        user = buyer()
        self.client.force_login(user, backend='users.backends.CustomerOTPBackend')
        response = self.client.patch('/api/v1/me/', {'name': 'New name', 'phone': '+447911123456'}, format='json')
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.name, 'New name')

    def test_profile_rejects_role_and_passport(self):
        self.client.force_login(buyer(), backend='users.backends.CustomerOTPBackend')
        response = self.client.patch('/api/v1/me/', {'staff_role': 'ADMIN', 'passport_number': 'not-allowed'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_invalid_phone_is_rejected(self):
        self.client.force_login(buyer(), backend='users.backends.CustomerOTPBackend')
        self.assertEqual(self.client.patch('/api/v1/me/', {'phone': '123'}, format='json').status_code, 400)

    def test_logout(self):
        self.client.force_login(buyer(), backend='users.backends.CustomerOTPBackend')
        self.assertEqual(self.client.post('/api/v1/auth/logout/', {}, format='json').status_code, 204)
        self.assertEqual(self.client.get('/api/v1/me/').status_code, 401)

    def test_staff_password_login(self):
        staff = manager()
        response = self.client.post('/api/v1/auth/staff/login/', {'email': staff.email, 'password': PASSWORD}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/v1/staff/orders/').status_code, 200)

    def test_customer_cannot_access_staff(self):
        self.client.force_login(buyer(), backend='users.backends.CustomerOTPBackend')
        self.assertEqual(self.client.get('/api/v1/staff/orders/').status_code, 403)

    def test_staff_customer_session_does_not_open_ops(self):
        staff = manager()
        self.client.force_login(staff, backend='users.backends.CustomerOTPBackend')
        self.assertEqual(self.client.get('/api/v1/staff/orders/').status_code, 403)
        self.assertEqual(self.client.get('/ops/').status_code, 302)

    def test_login_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post('/api/v1/auth/otp/request/', {'email': 'csrf@example.com'}, format='json')
        self.assertEqual(response.status_code, 403)
        token = client.get('/api/v1/auth/csrf/').json()['csrf_token']
        response = client.post('/api/v1/auth/otp/request/', {'email': 'csrf@example.com'}, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)

    def test_staff_password_login_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post('/api/v1/auth/staff/login/', {'email': 'staff@example.com', 'password': PASSWORD}, format='json')
        self.assertEqual(response.status_code, 403)
