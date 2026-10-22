from .base import *  # noqa: F403
from config.env import env_bool

DEBUG = env_bool("DJANGO_DEBUG", True)
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

import os
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND') or 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL') or 'development@localhost'
PUBLIC_FORMS_ENABLED = env_bool('PUBLIC_FORMS_ENABLED', True)
ORDER_INTAKE_ENABLED = env_bool('ORDER_INTAKE_ENABLED', True)
CLIENT_ANALYTICS_ENABLED = env_bool('CLIENT_ANALYTICS_ENABLED', True)
