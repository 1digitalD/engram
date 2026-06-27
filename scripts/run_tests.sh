#!/bin/bash
# Wrapper to run pytest with correct test DB env.
# The literal test password is `engram` — matches docker-compose.test.yml.
set -euo pipefail
cd /Volumes/lex1t/dev/shared/repos/engram
export PGPASSWORD="engram"
export PYTHONPATH=.
export TEST_DATABASE_URL="postgresql://engram:engram@127.0.0.1:5433/engram_test"
exec ./venv/bin/pytest -q "$@"
