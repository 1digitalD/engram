#!/usr/bin/env bash
# Compare current Flask route table against the v6 baseline fixture.
# Exit 0 when identical; exit 1 with unified diff on mismatch.
#
# Usage:
#   bash scripts/v6_route_table_diff.sh
#   bash scripts/v6_route_table_diff.sh --write-baseline   # refresh baseline (overseer only)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
BASELINE="$REPO/docs/v6/fixtures/route_table_baseline.txt"
CURRENT="$(mktemp)"

cleanup() { rm -f "$CURRENT"; }
trap cleanup EXIT

cd "$REPO"
export TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql://engram:engram@localhost:5433/engram_test}"

./venv/bin/flask --app app.py routes 2>/dev/null \
  | awk '{print $1, $2, $3}' \
  | sort > "$CURRENT"

if [[ "${1:-}" == "--write-baseline" ]]; then
  cp "$CURRENT" "$BASELINE"
  echo "Wrote baseline ($(wc -l < "$BASELINE" | tr -d ' ') routes) to $BASELINE"
  exit 0
fi

if [[ ! -f "$BASELINE" ]]; then
  echo "Missing baseline: $BASELINE" >&2
  echo "Run: bash scripts/v6_route_table_diff.sh --write-baseline" >&2
  exit 2
fi

if diff -u "$BASELINE" "$CURRENT"; then
  echo "Route table matches baseline ($(wc -l < "$BASELINE" | tr -d ' ') routes)."
else
  echo "Route table differs from baseline." >&2
  exit 1
fi
