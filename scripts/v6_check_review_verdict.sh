#!/usr/bin/env bash
# Verify a formal code-review verdict file exists and approves.
#
# Usage: bash scripts/v6_check_review_verdict.sh <implement-task-id>
# Example: bash scripts/v6_check_review_verdict.sh v6-10-report-assembler
#
# Looks for docs/v6/reviews/<implement-task-id>.md containing "Verdict: APPROVE".
set -euo pipefail

TASK_ID="${1:-}"
if [[ -z "$TASK_ID" ]]; then
  echo "Usage: $0 <implement-task-id>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERDICT_FILE="$SCRIPT_DIR/../docs/v6/reviews/${TASK_ID}.md"

if [[ ! -f "$VERDICT_FILE" ]]; then
  echo "Missing review verdict: $VERDICT_FILE" >&2
  exit 1
fi

if ! grep -qE '^(\*\*)?Verdict:(\*\*)? APPROVE' "$VERDICT_FILE"; then
  echo "Review verdict is not APPROVE in $VERDICT_FILE" >&2
  grep -E '^(\*\*)?Verdict:' "$VERDICT_FILE" >&2 || echo "(no Verdict line found)" >&2
  exit 1
fi

for pass in 1 2 3 4 5; do
  if ! grep -qE "Pass ${pass}.*PASS" "$VERDICT_FILE"; then
    echo "Pass ${pass} not marked PASS in $VERDICT_FILE" >&2
    exit 1
  fi
done

echo "OK review verdict: $VERDICT_FILE (Verdict: APPROVE, Passes 1-5 PASS)"
