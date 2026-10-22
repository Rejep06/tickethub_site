from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APITestCase


class FoundationApiTests(APITestCase):
    def test_public_api_reports_mvp_capabilities(self):
        response = self.client.get("/api/v1/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["implementation_stage"], "BACKEND_MVP")
        self.assertTrue(response.data["order_intake_enabled"])
        self.assertFalse(response.data["online_payments_enabled"])

    def test_live(self):
        response = self.client.get("/health/live/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_ready_queries_postgresql(self):
        response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 200)

    def test_ready_does_not_leak_driver_error(self):
        with patch("core.views.connection.cursor", side_effect=OperationalError("sensitive-connection-details")):
            response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotIn(b"sensitive", response.content)

    def test_request_id_and_no_store(self):
        response = self.client.get("/api/v1/")
        uuid.UUID(response["X-Request-ID"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_csrf_cookie_endpoint(self):
        response = self.client.get("/api/v1/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)
        self.assertTrue(response.json()["csrf_token"])

    def test_missing_api_is_json_not_fake_success(self):
        response = self.client.get("/api/v1/does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "NOT_FOUND")

    def test_schema_is_not_public(self):
        response = self.client.get("/api/v1/schema/")
        self.assertEqual(response.status_code, 401)


@override_settings(ROOT_URLCONF="core.tests.urls")
class SessionSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = get_user_model().objects.create_user("buyer@example.com")

    def test_missing_auth_is_401(self):
        response = self.client.post("/api/v1/test-private/", {}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "AUTH_REQUIRED")

    def test_authenticated_post_without_csrf_is_forbidden(self):
        self.client.force_login(self.user)
        response = self.client.post("/api/v1/test-private/", {}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_authenticated_post_with_csrf(self):
        self.client.force_login(self.user)
        token = self.client.get("/api/v1/auth/csrf/").json()["csrf_token"]
        response = self.client.post("/api/v1/test-private/", {}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
