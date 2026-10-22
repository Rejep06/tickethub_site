#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
[ -f .env.production ] || { echo 'Create .env.production first.' >&2; exit 1; }
exec docker compose --env-file .env.production -f compose.production.yml "$@"
