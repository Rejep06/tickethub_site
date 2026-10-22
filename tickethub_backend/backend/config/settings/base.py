import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from config.env import env_bool, env_int, env_list

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY. Use scripts/create_local_env.py locally.")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "core.apps.TickethubAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "users.apps.UsersConfig",
    "core.apps.CoreConfig",
    "events",
    "venues",
    "tickets",
    "orders",
    "promotions",
    "ticket_requests",
    "payments",
    "analytics",
    "external_events",

]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.RequestIdMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.StaffSessionTimeoutMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.PrivateResponseMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.environ.get("POSTGRES_DB", "tickethub"),
    "USER": os.environ.get("POSTGRES_USER", "tickethub"),
    "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
    "HOST": os.environ.get("POSTGRES_HOST", "db"),
    "PORT": env_int("POSTGRES_PORT", 5432, minimum=1),
    "CONN_MAX_AGE": 60,
    "CONN_HEALTH_CHECKS": True,
    "OPTIONS": {"connect_timeout": 5},
}}
# The project uses this model before the first migration, never auth.User.
AUTH_USER_MODEL = "users.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "ru"
LANGUAGES = [("ru", "Русский"), ("en", "English")]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 30 * 24 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "core.views.csrf_failure"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
LOGIN_URL = "/ops/login/"
LOGIN_REDIRECT_URL = "/ops/"
LOGOUT_REDIRECT_URL = "/ops/login/"
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["core.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardPagination",
    "PAGE_SIZE": 24,
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Tickethub API",
    "DESCRIPTION": "Tickethub REST API. Money amounts are integer RUB kopecks.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_AUTHENTICATION": ["core.authentication.SessionAuthentication"],
    "SERVE_PERMISSIONS": ["core.permissions.IsStaff"],
    "COMPONENT_SPLIT_REQUEST": True,
}
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587, minimum=1)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured("Choose EMAIL_USE_TLS or EMAIL_USE_SSL, not both.")
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Production intake stays disabled until contacts and approved legal pages are configured.
PUBLIC_FORMS_ENABLED = env_bool("PUBLIC_FORMS_ENABLED", False)
ORDER_INTAKE_ENABLED = env_bool("ORDER_INTAKE_ENABLED", False)
CLIENT_ANALYTICS_ENABLED = env_bool("CLIENT_ANALYTICS_ENABLED", False)
PAYMENT_MODE = "disabled"
TICKET_DOWNLOAD_ENABLED = False

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "{levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {"django.db.backends": {"handlers": ["console"], "level": "WARNING", "propagate": False}},
}

AUTHENTICATION_BACKENDS = ['users.backends.StaffPasswordBackend', 'users.backends.CustomerOTPBackend']
TRUST_PROXY_IP = False
DIRECT_ORDER_LIMIT = 10
REQUEST_LIMIT = 100
HOLD_SECONDS = 600
CONTACT_EMAIL = os.environ.get('CONTACT_EMAIL', '')
CONTACT_PHONE = os.environ.get('CONTACT_PHONE', '')
CONTACT_HOURS = os.environ.get('CONTACT_HOURS', '')
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:8000').rstrip('/')
EMAIL_MESSAGE_DOMAIN = os.environ.get('EMAIL_MESSAGE_DOMAIN', 'localhost')
STAFF_NOTIFICATION_EMAILS = env_list('STAFF_NOTIFICATION_EMAILS')
REQUIRE_LEGAL_ACCEPTANCE = env_bool('REQUIRE_LEGAL_ACCEPTANCE', False)
REQUIRED_LEGAL_SLUGS = ['privacy', 'offer', 'refund-policy']
REPORT_TIMEZONE = 'Europe/Moscow'

ALLOW_DEMO_DATA = env_bool('ALLOW_DEMO_DATA', False)

# Read-only PortalBilet import. No customer holds or provider purchases.
PORTALBILET_HTTP_TIMEOUT = env_int("PORTALBILET_HTTP_TIMEOUT", 8, minimum=1)
PORTALBILET_IMPORT_BUDGET = env_int("PORTALBILET_IMPORT_BUDGET", 35, minimum=10)
PORTALBILET_MAX_RESPONSE_BYTES = env_int("PORTALBILET_MAX_RESPONSE_BYTES", 8 * 1024 * 1024, minimum=1024)
PORTALBILET_SNAPSHOT_BYTES = env_int("PORTALBILET_SNAPSHOT_BYTES", 512 * 1024, minimum=1024)
PORTALBILET_MAX_DATES = env_int("PORTALBILET_MAX_DATES", 20, minimum=1)
PORTALBILET_SYNC_MINUTES = env_int("PORTALBILET_SYNC_MINUTES", 360, minimum=15)
