import uuid

from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

User = get_user_model()


class UserModelTests(TestCase):
    def test_custom_user_is_configured(self):
        self.assertEqual(User._meta.label, "users.User")
        self.assertEqual(User.USERNAME_FIELD, "email")
        self.assertEqual(User.REQUIRED_FIELDS, [])

    def test_customer_has_uuid_and_no_password(self):
        user = User.objects.create_user(" Customer@Example.COM ", name="Клиент")
        self.assertIsInstance(user.pk, uuid.UUID)
        self.assertEqual(user.email, "customer@example.com")
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.staff_role, "")
        self.assertIsNone(user.email_verified_at)

    def test_password_is_hashed(self):
        password = "Example-test-password!2026"
        user = User.objects.create_user("buyer@example.com", password=password)
        self.assertNotEqual(user.password, password)
        self.assertTrue(user.check_password(password))

    def test_email_is_required(self):
        with self.assertRaises(ValueError):
            User.objects.create_user("")

    def test_email_case_unique_even_bypassing_save(self):
        User.objects.create_user("buyer@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.bulk_create([User(email="BUYER@example.com", password="!")])

    def test_manager_has_staff_flag_but_not_superuser(self):
        user = User.objects.create_user("manager@example.com", password="Example-test-password!2026", staff_role="MANAGER")
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_staff_account_requires_password(self):
        with self.assertRaises(ValueError):
            User.objects.create_user("manager@example.com", staff_role="MANAGER")

    def test_superuser_defaults(self):
        user = User.objects.create_superuser("admin@example.com", "Example-test-password!2026")
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.staff_role, "ADMIN")

    def test_superuser_cannot_be_manager(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser("admin@example.com", "Example-test-password!2026", staff_role="MANAGER")

    def test_database_rejects_inconsistent_staff_flag(self):
        user = User.objects.create_user("buyer@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=user.pk).update(is_staff=True)

    def test_database_rejects_customer_superuser(self):
        user = User.objects.create_user("buyer@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=user.pk).update(is_superuser=True)

    def test_role_update_updates_derived_flag(self):
        user = User.objects.create_user("buyer@example.com")
        user.set_password("Example-test-password!2026")
        user.staff_role = "MANAGER"
        user.save(update_fields=["staff_role", "password"])
        user.refresh_from_db()
        self.assertTrue(user.is_staff)

    def test_authentication_accepts_email_case(self):
        user = User.objects.create_superuser("admin@example.com", "Example-test-password!2026")
        result = authenticate(email="ADMIN@EXAMPLE.COM", password="Example-test-password!2026")
        self.assertEqual(result, user)

    def test_inactive_user_cannot_authenticate(self):
        user = User.objects.create_superuser("admin@example.com", "Example-test-password!2026")
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.assertIsNone(authenticate(email=user.email, password="Example-test-password!2026"))

    def test_no_document_fields(self):
        field_names = {field.name for field in User._meta.get_fields()}
        for name in ("passport", "passport_number", "passport_series", "gosuslugi_password", "fan_id_number"):
            self.assertNotIn(name, field_names)
