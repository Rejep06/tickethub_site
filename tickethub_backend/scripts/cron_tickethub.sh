#!/bin/sh
# The host cron invokes only finite, explicit maintenance commands.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
dc() { docker compose --env-file "${PRODUCTION_ENV_FILE:-.env.production}" -f compose.prod.yaml "$@"; }
dc exec -T backend python manage.py cleanup_expired_holds
dc exec -T backend python manage.py cleanup_expired_quotes
dc exec -T backend python manage.py remind_staff
