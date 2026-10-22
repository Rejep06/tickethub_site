#!/bin/sh
# A fresh isolated PostgreSQL volume on EVERY run. Does not delete development/production data.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
command -v docker >/dev/null 2>&1 || { echo "BLOCKED: Docker is not installed." >&2; exit 1; }
docker compose version >/dev/null
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required to create isolated secrets." >&2; exit 1; }
umask 077
ID=$(python3 -c 'import secrets; print(secrets.token_hex(6))')
PROJECT="tickethub-verify-$ID"
TEMP_ENV="$ROOT/.env.verify-$ID"
export TICKETHUB_ENV_FILE="$TEMP_ENV"
python3 - "$TEMP_ENV" <<'PYENV'
import importlib.util, pathlib, sys
spec = importlib.util.spec_from_file_location('local_env', 'scripts/create_local_env.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.create_env(pathlib.Path(sys.argv[1]))
PYENV
dc() { docker compose --env-file "$TEMP_ENV" -p "$PROJECT" -f compose.yaml -f compose.verify.yaml "$@"; }
cleanup() {
    docker rm -f "$PROJECT-api" >/dev/null 2>&1 || true
    # PROJECT is always the random verification project created above.
    dc down --volumes --remove-orphans >/dev/null 2>&1 || true
    rm -f "$TEMP_ENV"
}
trap cleanup EXIT HUP INT TERM
mkdir -p docs/verification
printf '%s\n' 'CHECK: Compose, image build, fresh PostgreSQL'
dc config --quiet
dc build api
dc up -d --wait db
printf '%s\n' 'CHECK: migration definitions and clean database migrate'
dc run --rm --no-deps api python manage.py makemigrations --check --dry-run --settings=config.settings.test
dc run --rm --no-deps api python manage.py migrate --noinput --settings=config.settings.test
dc run --rm --no-deps api python manage.py check --settings=config.settings.test
printf '%s\n' 'CHECK: Django / DRF / real PostgreSQL concurrency tests'
dc run --rm --no-deps api python manage.py test --noinput --verbosity=2 --settings=config.settings.test
printf '%s\n' 'CHECK: demo command twice (idempotence)'
dc run --rm --no-deps api python manage.py seed_demo --settings=config.settings.test
dc run --rm --no-deps api python manage.py seed_demo --settings=config.settings.test
printf '%s\n' 'CHECK: actual API process, HTTP health, catalog and admin login page'
dc run --no-deps -d --name "$PROJECT-api" api gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 >/dev/null
docker exec -i "$PROJECT-api" python - <<'PYHTTP'
import time, urllib.request, urllib.error
for attempt in range(30):
    try:
        urllib.request.urlopen('http://127.0.0.1:8000/health/ready/', timeout=3)
        break
    except (urllib.error.URLError, OSError):
        time.sleep(1)
else:
    raise SystemExit('API readiness failed')
for path in ['/health/live/', '/health/ready/', '/api/v1/events/', '/ops/login/']:
    response = urllib.request.urlopen('http://127.0.0.1:8000' + path, timeout=5)
    assert response.status == 200, (path, response.status)
    print(path, response.status)
PYHTTP
docker exec "$PROJECT-api" pip freeze > docs/verification/requirements.executed.txt
printf '%s\n' 'VERIFIED by this run. Promote requirements.executed.txt to backend/requirements.lock only after review.'
