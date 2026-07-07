#!/usr/bin/env bash
# Poll Loopsmith drain status/blockers for the active prd.json iteration.
# Intended to be run every ~5 minutes (cron, launchd, or a Monitor loop) while a
# `host-run --drain` is active in the background. Prints one line on state change
# or blocker; silent (no output) when nothing new to report, so it's safe to run
# unattended without spamming.
#
# Usage: scripts/loopsmith_poll_status.sh [--repo <path>] [--state-file <path>]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${SCRIPT_DIR}/.."
STATE_FILE="/tmp/loopsmith_poll_state_engram.json"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --state-file) STATE_FILE="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
REPO="$(cd "$REPO" && pwd)"

export LOOPSMITHCTL="${LOOPSMITHCTL:-/Users/danish/plugins/loopsmith-orchestrator/scripts/loopsmithctl.py}"
LCS_ENV="/Volumes/lex1t/dev/shared/repos/loopsmith-coding-standards/scripts/lcs-env.sh"
# shellcheck disable=SC1090
[[ -f "$LCS_ENV" ]] && source "$LCS_ENV"

# Read state straight from prd.json rather than `loopsmithctl status` — status
# blocks/hangs while a drain holds the repo lock, which is exactly when polling
# needs to keep working.
PRD_SUMMARY="$(python3 -c '
import json, sys
try:
    with open(sys.argv[1]) as f:
        prd = json.load(f)
except Exception as exc:
    print(json.dumps({"error": str(exc)}))
    sys.exit(0)
tasks = prd.get("tasks") or []
summary = [
    {
        "id": t.get("id"),
        "blocked": t.get("blocked"),
        "passes": t.get("passes"),
        "attempts": t.get("attempts"),
        "blockerReason": t.get("blockerReason"),
    }
    for t in tasks
]
print(json.dumps({"iteration": prd.get("iteration"), "tasks": summary}, sort_keys=True))
' "$REPO/prd.json")"

PREV=""
[[ -f "$STATE_FILE" ]] && PREV="$(cat "$STATE_FILE")"

ITERATION_NAME="$(echo "$PRD_SUMMARY" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("iteration","unknown"))')"

if [[ "$PRD_SUMMARY" != "$PREV" ]]; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ${ITERATION_NAME} state changed:"
  echo "$PRD_SUMMARY" | python3 -m json.tool
  echo "$PRD_SUMMARY" > "$STATE_FILE"
fi

BLOCKED_COUNT="$(echo "$PRD_SUMMARY" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(sum(1 for t in d.get("tasks", []) if t.get("blocked")))
')"
if [[ "$BLOCKED_COUNT" != "0" ]]; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) BLOCKER: $BLOCKED_COUNT task(s) blocked in ${ITERATION_NAME}"
fi

if ! pgrep -f "loopsmithctl.py host-run --repo $REPO --drain" >/dev/null 2>&1; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) NOTE: no active drain process found for $REPO"
fi
