from django.contrib.auth import get_user_model
from django.test import Client, TestCase

User = get_user_model()
PASSWORD = "Example-test-password!2026"


class AdminTests(TestCase):
    def test_admin_email_password_login(self):
        User.objects.create_superuser("admin@example.com", PASSWORD)
        response = self.client.post("/ops/login/?next=/ops/", {
            "username": "admin@example.com", "password": PASSWORD, "next": "/ops/",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/ops/").status_code, 200)
        self.assertEqual(self.client.get("/ops/users/user/").status_code, 200)

    def test_customer_cannot_open_admin(self):
        user = User.objects.create_user("buyer@example.com", PASSWORD)
        self.client.force_login(user)
        self.assertEqual(self.client.get("/ops/").status_code, 302)

    def test_manager_cannot_edit_users(self):
        manager = User.objects.create_user("manager@example.com", PASSWORD, staff_role="MANAGER")
        self.client.force_login(manager)
        self.assertEqual(self.client.get("/ops/users/user/").status_code, 200)
        self.assertEqual(self.client.get("/ops/users/user/add/").status_code, 403)

    def test_admin_login_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post("/ops/login/", {"username": "admin@example.com", "password": PASSWORD})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "CSRF_FAILED")
