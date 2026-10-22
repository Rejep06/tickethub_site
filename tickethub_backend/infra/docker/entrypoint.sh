#!/bin/sh
set -eu
# Migrations are an explicit deployment step, never a loop in every web worker.
exec "$@"
