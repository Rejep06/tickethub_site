#!/bin/sh
# Consistent DB snapshot; stop image uploads during this command for DB/media alignment.
set -eu
umask 077
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
TARGET="${1:-$ROOT/backups-live}/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$TARGET"
# File redirection here is a Linux shell, not the Windows PowerShell binary pipeline.
sh deploy/prod.sh exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-acl' > "$TARGET/database.dump"
sh deploy/prod.sh exec -T backend tar -C /app/media -czf - . > "$TARGET/media.tar.gz"
cp .env.production "$TARGET/env.production.private"
cp compose.production.yml "$TARGET/compose.production.yml"
cp tickethub_frontend/package-lock.json "$TARGET/package-lock.json"
[ ! -f tickethub_backend/backend/requirements.lock ] || cp tickethub_backend/backend/requirements.lock "$TARGET/requirements.lock"
(cd "$TARGET" && sha256sum database.dump media.tar.gz env.production.private > SHA256SUMS)
printf 'Backup saved to %s\nKeep it private, encrypted off-server, and test restoring it.\n' "$TARGET"
