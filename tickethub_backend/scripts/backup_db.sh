#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
umask 077
ENV_FILE=${PRODUCTION_ENV_FILE:-.env.production}
DEST=${1:-backups}
mkdir -p "$DEST"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
TARGET="$DEST/tickethub-$STAMP.dump"
[ ! -e "$TARGET" ] || { echo 'Backup destination already exists.' >&2; exit 1; }
TEMP="$TARGET.partial"
trap 'rm -f "$TEMP"' EXIT HUP INT TERM
docker compose --env-file "$ENV_FILE" -f compose.prod.yaml exec -T db \
  sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$TEMP"
test -s "$TEMP"
mv "$TEMP" "$TARGET"
printf 'Created %s\n' "$TARGET"
