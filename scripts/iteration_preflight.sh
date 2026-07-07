#!/usr/bin/env bash
# Preflight checks before starting a Loopsmith drain on engram.
#
# Usage: bash scripts/iteration_preflight.sh [repo-path]
set -euo pipefail

REPO="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$REPO"

echo "== iteration preflight: $REPO =="

# prd.json must parse
python3 -c 'import json, sys; json.load(open(sys.argv[1]))' "$REPO/prd.json"
echo "OK prd.json parses"

ITERATION="$(python3 -c 'import json; print(json.load(open("prd.json"))["iteration"])')"
echo "OK iteration: $ITERATION"

# No stray dirty files except allowed contract paths during active drain
DIRTY="$(git status --porcelain | grep -v '^.. prd.json$' | grep -v '^.. EXECUTION-TRACKER.md$' | grep -v '^.. AGENTS.md$' || true)"
if [[ -n "$DIRTY" ]]; then
  echo "WARN dirty repo (commit or stash before drain):" >&2
  echo "$DIRTY" >&2
  exit 1
fi
echo "OK working tree clean"

# Test DB reachable
export TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql://engram:engram@localhost:5433/engram_test}"
./venv/bin/python -c "
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['TEST_DATABASE_URL'])
with engine.connect() as conn:
    conn.execute(text('SELECT 1'))
print('OK test database reachable')
"

# Optional LCS prd validator when installed
LCS_VALIDATE="/Volumes/lex1t/dev/shared/repos/loopsmith-coding-standards/scripts/validate-prd-lcs.sh"
if [[ -x "$LCS_VALIDATE" ]]; then
  bash "$LCS_VALIDATE" "$REPO/prd.json"
  echo "OK LCS prd validation"
else
  echo "SKIP LCS validate-prd-lcs.sh not found"
fi

echo "== preflight passed — safe to start drain =="
