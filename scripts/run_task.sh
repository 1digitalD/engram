#!/usr/bin/env bash
# Re-run a single task from AGENT_PLAN.md.
# Usage: bash scripts/run_task.sh C1-MODELS
set -euo pipefail

TASK_ID="${1:?Usage: run_task.sh <TASK_ID>}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$REPO_DIR/.env" ] && source "$REPO_DIR/.env"

prompt=$(cat <<PROMPT
You are working in the Engram v2 repository at: $REPO_DIR

Your task: Execute ONLY task ${TASK_ID} from docs/AGENT_PLAN.md.

Before writing any code:
1. Read AGENTS.md
2. Read docs/AGENT_PLAN.md and find task ${TASK_ID}
3. Read every file listed in the task's "Reads" section

TDD process (mandatory):
1. Write the test file(s) listed in "Writes"
2. Run validation — confirm tests FAIL
3. Implement
4. Run validation — confirm tests PASS
5. Run full suite: PYTHONPATH=. pytest -q — confirm no regressions

Update EXECUTION-TRACKER.md when done. Report changed files, test output, coverage, blockers.

Only touch files in the task's "Writes" list.
PROMPT
)

echo "Running task $TASK_ID..."
claude --print -p "$prompt" 2>&1 | tee "$REPO_DIR/logs/tasks/${TASK_ID}-rerun-$(date +%H%M).log"
