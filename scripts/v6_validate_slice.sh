#!/usr/bin/env bash
# Standard per-slice validation for v6 Loopsmith tasks.
# Runs focused backend checks; optional route-table diff when CHECK_ROUTES=1.
#
# Usage:
#   bash scripts/v6_validate_slice.sh
#   CHECK_ROUTES=1 bash scripts/v6_validate_slice.sh
#   EXTRA_PYTEST="tests/integration/test_foo.py" bash scripts/v6_validate_slice.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO"

export TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql://engram:engram@localhost:5433/engram_test}"

echo "== v6 slice validation (TEST_DATABASE_URL=$TEST_DATABASE_URL) =="

if [[ -n "${EXTRA_PYTEST:-}" ]]; then
  echo "-- focused pytest: $EXTRA_PYTEST"
  ./venv/bin/pytest -q $EXTRA_PYTEST
fi

echo "-- full backend suite (serial)"
./venv/bin/pytest -q

if [[ "${CHECK_ROUTES:-0}" == "1" ]]; then
  echo "-- route table parity"
  bash scripts/v6_route_table_diff.sh
fi

echo "== slice validation OK =="
