#!/bin/sh
set -eu
# Runs once on a new production volume. The web process never receives the bootstrap password.
psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=appuser="$POSTGRES_APP_USER" --set=apppass="$POSTGRES_APP_PASSWORD" --set=dbname="$POSTGRES_DB" <<'SQL'
CREATE ROLE :"appuser" LOGIN PASSWORD :'apppass' NOSUPERUSER NOCREATEDB NOCREATEROLE;
ALTER DATABASE :"dbname" OWNER TO :"appuser";
GRANT ALL ON SCHEMA public TO :"appuser";
SQL
