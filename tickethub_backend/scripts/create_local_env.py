#!/usr/bin/env python3
"""Create a local .env once, with random secrets; never print them."""
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def create_env(destination: Path) -> None:
    values = {
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
        "DJANGO_DEBUG": "true",
        "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "http://localhost:8000,http://127.0.0.1:8000",
        "POSTGRES_DB": "tickethub",
        "POSTGRES_USER": "tickethub",
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "POSTGRES_HOST": "db",
        "POSTGRES_PORT": "5432",
        "EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend",
        "PUBLIC_FORMS_ENABLED": "true",
        "ORDER_INTAKE_ENABLED": "true",
        "CLIENT_ANALYTICS_ENABLED": "true",
        "REQUIRE_LEGAL_ACCEPTANCE": "false",
        "CONTACT_EMAIL": "",
        "CONTACT_PHONE": "",
        "CONTACT_HOURS": "",
        "SITE_URL": "http://localhost:8000",
        "STAFF_NOTIFICATION_EMAILS": "",
        "EMAIL_MESSAGE_DOMAIN": "localhost",
        "EMAIL_HOST": "",
        "EMAIL_PORT": "587",
        "EMAIL_HOST_USER": "",
        "EMAIL_HOST_PASSWORD": "",
        "EMAIL_USE_TLS": "true",
        "EMAIL_USE_SSL": "false",
        "DEFAULT_FROM_EMAIL": "",
        "LOCAL_UID": str(os.getuid()) if hasattr(os, "getuid") else "1000",
        "LOCAL_GID": str(os.getgid()) if hasattr(os, "getgid") else "1000",
    }
    # O_EXCL refuses to overwrite an existing file, including a symlink.
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write("# Local development secrets. Do not commit or share this file.\n")
        for name, value in values.items():
            stream.write(f"{name}={value}\n")


if __name__ == "__main__":
    try:
        create_env(ROOT / ".env")
    except FileExistsError:
        raise SystemExit(".env already exists; nothing was overwritten.")
    print("Created .env for local development. Secret values were not printed.")
