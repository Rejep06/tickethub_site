#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
sh deploy/prod.sh run --rm --no-deps certbot renew --webroot -w /var/www/acme --quiet "$@"
sh deploy/prod.sh exec -T nginx nginx -t
sh deploy/prod.sh exec -T nginx nginx -s reload
