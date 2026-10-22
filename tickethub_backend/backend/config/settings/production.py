"""Security baseline, not a certified production deployment."""
from django.core.exceptions import ImproperlyConfigured
from .base import *  # noqa: F403

DEBUG = False
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("Production requires a random secret of at least 50 characters.")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS or "localhost" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Production requires explicit public DJANGO_ALLOWED_HOSTS.")
if not DATABASES["default"]["PASSWORD"]:
    raise ImproperlyConfigured("Set a PostgreSQL password in production.")
if not CSRF_TRUSTED_ORIGINS or any(not origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured("Set explicit https:// DJANGO_CSRF_TRUSTED_ORIGINS.")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
# Enable only behind the supplied trusted reverse proxy, never expose Gunicorn directly.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

TRUST_PROXY_IP = True
REQUIRE_LEGAL_ACCEPTANCE = True
if EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend':
    raise ImproperlyConfigured('Production permits SMTP email only.')
if (PUBLIC_FORMS_ENABLED or ORDER_INTAKE_ENABLED) and (not EMAIL_HOST or not DEFAULT_FROM_EMAIL or not CONTACT_EMAIL or not CONTACT_PHONE):
    raise ImproperlyConfigured('Set SMTP and real project contacts before enabling forms.')

ALLOW_DEMO_DATA = False

SECURE_REDIRECT_EXEMPT = [r'^health/(live|ready)/$']
# Only loopback is added for the container's internal health probe. Gunicorn has no host port.
ALLOWED_HOSTS = [*ALLOWED_HOSTS, '127.0.0.1']
