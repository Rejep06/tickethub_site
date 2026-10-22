#!/bin/sh
# Resolve on a connected machine using the SAME Python image as the application.
# No guessed versions are written by this script; failure never replaces an existing lock.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
IMAGE=$(python3 deploy/env_value.py PYTHON_IMAGE)
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT HUP INT TERM
docker run --rm -v "$ROOT/tickethub_backend/backend/requirements.txt:/requirements.txt:ro" "$IMAGE"   sh -c 'python -m venv /tmp/lockenv && /tmp/lockenv/bin/pip install --disable-pip-version-check -r /requirements.txt >&2 && /tmp/lockenv/bin/pip check >&2 && /tmp/lockenv/bin/pip freeze' > "$TMP"
[ -s "$TMP" ]
cp "$TMP" tickethub_backend/backend/requirements.lock
echo 'Resolved requirements.lock. Review it, run the isolated tests, then build. Save this lock with the release.'
