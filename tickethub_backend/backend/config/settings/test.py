from .base import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
DATABASES["default"]["CONN_MAX_AGE"] = 0
# No SQLite fallback: all database tests must exercise PostgreSQL.

PUBLIC_FORMS_ENABLED = True
ORDER_INTAKE_ENABLED = True
CLIENT_ANALYTICS_ENABLED = True
DEFAULT_FROM_EMAIL = 'test@example.com'
STAFF_NOTIFICATION_EMAILS = []
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

ALLOW_DEMO_DATA = True
