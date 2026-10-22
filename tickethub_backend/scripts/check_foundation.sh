#!/bin/sh
# Compatibility entry point; the project now verifies the full backend.
set -eu
exec sh "$(dirname "$0")/verify_backend.sh" "$@"
