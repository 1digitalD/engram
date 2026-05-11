#!/usr/bin/env bash
# =============================================================================
# Engram v2 — Overnight Build Orchestrator
# =============================================================================
# Runs Cycle 1 tasks sequentially, validates after each, writes morning report.
#
# Prerequisites (must be done before running this):
#   1. Docker running + postgres container healthy (docker compose up -d)
#   2. .env file present with DATABASE_URL, TEST_DATABASE_URL, OPENAI_API_KEY, ANTHROPIC_API_KEY
#   3. docs/SCHEMA.sql applied to both DBs (scripts/apply_schema.sh)
#   4. Python venv active with requirements installed
#
# Usage:
#   bash scripts/build_overnight.sh 2>&1 | tee logs/overnight.log
# =============================================================================

set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# macOS 26 + Homebrew Python libexpat fix
export DYLD_LIBRARY_PATH="/opt/homebrew/Cellar/expat/2.8.0/lib:${DYLD_LIBRARY_PATH:-}"
export PYTHON="$REPO_DIR/.venv/bin/python"
export PYTHONPATH="$REPO_DIR"
LOG_DIR="$REPO_DIR/logs"
REPORT="$LOG_DIR/morning_report.md"
TASK_LOG_DIR="$LOG_DIR/tasks"
START_TIME=$(date +%s)

mkdir -p "$LOG_DIR" "$TASK_LOG_DIR"

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()  { echo -e "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_DIR/orchestrator.log"; }
ok()   { log "${GREEN}✓ $1${NC}"; }
fail() { log "${RED}✗ $1${NC}"; }
warn() { log "${YELLOW}⚠ $1${NC}"; }

# ── Prerequisite checks ───────────────────────────────────────────────────────
check_prereqs() {
    log "Checking prerequisites..."

    # .env
    [ -f "$REPO_DIR/.env" ] || { fail ".env not found — copy .env.example and fill in API keys"; exit 1; }
    source "$REPO_DIR/.env"

    # Required env vars
    for var in DATABASE_URL TEST_DATABASE_URL OPENAI_API_KEY ANTHROPIC_API_KEY; do
        [ -n "${!var:-}" ] || { fail "$var not set in .env"; exit 1; }
    done

    # Postgres reachable
    psql "$DATABASE_URL" -c "SELECT 1;" > /dev/null 2>&1 \
        || { fail "Cannot connect to DATABASE_URL — is Docker running?"; exit 1; }

    psql "$TEST_DATABASE_URL" -c "SELECT 1;" > /dev/null 2>&1 \
        || { fail "Cannot connect to TEST_DATABASE_URL"; exit 1; }

    # Schema applied (check entities table exists)
    psql "$TEST_DATABASE_URL" -c "\dt entities" 2>&1 | grep -q "entities" \
        || { fail "Schema not applied to test DB — run scripts/apply_schema.sh first"; exit 1; }

    # claude CLI available
    command -v claude > /dev/null 2>&1 \
        || { fail "'claude' CLI not found — install Claude Code"; exit 1; }

    # Python venv
    "$PYTHON" -c "import flask, sqlalchemy, psycopg2" > /dev/null 2>&1 \
        || { fail "Python dependencies missing — run: DYLD_LIBRARY_PATH=/opt/homebrew/Cellar/expat/2.8.0/lib .venv/bin/pip install -r requirements.txt"; exit 1; }

    ok "All prerequisites passed"
}

# ── Task runner ───────────────────────────────────────────────────────────────
PASSED_TASKS=()
FAILED_TASKS=()

run_task() {
    local task_id="$1"
    local validate_cmd="$2"
    local task_log="$TASK_LOG_DIR/${task_id}.log"

    log "━━━ Starting $task_id ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Build the agent prompt from the task spec
    local prompt
    prompt=$(cat <<PROMPT
You are working in the Engram v2 repository at: $REPO_DIR

Your task: Execute ONLY task ${task_id} from docs/AGENT_PLAN.md.

Before writing any code:
1. Read AGENTS.md
2. Read docs/PRD.md
3. Read docs/TECH_SPEC.md
4. Read docs/AGENT_PLAN.md and find task ${task_id}
5. Read every file listed in that task's "Reads" section

TDD process (mandatory):
1. Write the test file(s) listed in the task's "Writes" section
2. Run the validation command — confirm tests FAIL (they should, nothing is implemented yet)
3. Implement the code
4. Run the validation command again — confirm tests PASS
5. Run the full suite: PYTHONPATH=. pytest -q — confirm no regressions

When done:
- Update EXECUTION-TRACKER.md with your results (task id, status, test output, coverage, notes)
- Report: list of changed files, final test output, coverage %, any blockers

Constraints:
- Only touch files listed in the task's "Writes" section
- Do not touch tests/conftest.py without explicit coordination
- If blocked, write the blocker to EXECUTION-TRACKER.md and stop — do not improvise around it
PROMPT
)

    # Run claude non-interactively, capture output
    if claude --print -p "$prompt" > "$task_log" 2>&1; then
        ok "$task_id completed"
        PASSED_TASKS+=("$task_id")

        # Run validation
        log "Running validation for $task_id: $validate_cmd"
        if eval "$validate_cmd" >> "$task_log" 2>&1; then
            ok "$task_id validation passed"
        else
            fail "$task_id validation FAILED after implementation"
            FAILED_TASKS+=("${task_id}:validation")
            return 1
        fi
    else
        fail "$task_id FAILED (agent exited non-zero)"
        FAILED_TASKS+=("${task_id}:agent")
        return 1
    fi
}

# ── Morning report ────────────────────────────────────────────────────────────
write_report() {
    local end_time=$(date +%s)
    local elapsed=$(( end_time - START_TIME ))
    local hours=$(( elapsed / 3600 ))
    local minutes=$(( (elapsed % 3600) / 60 ))

    cat > "$REPORT" <<REPORT
# Engram v2 — Overnight Build Report
Generated: $(date '+%Y-%m-%d %H:%M:%S')
Duration: ${hours}h ${minutes}m

## Summary

| Result | Tasks |
|---|---|
| ✓ Passed | $(IFS=,; echo "${PASSED_TASKS[*]:-none}") |
| ✗ Failed | $(IFS=,; echo "${FAILED_TASKS[*]:-none}") |

## What to do this morning

$(if [ ${#FAILED_TASKS[@]} -eq 0 ]; then
cat <<MORNING
All Cycle 1 tasks completed. Run this to verify:

\`\`\`bash
source .env
PYTHONPATH=. pytest -q --cov=. --cov-report=term-missing
cd ui && npm run build
\`\`\`

If green, you are ready to start Cycle 2 (C2-LINKS-API, C2-EDITOR, C2-KANBAN, C2-SURFACING).
MORNING
else
cat <<MORNING
Some tasks failed. For each failed task:
1. Check logs/tasks/<task_id>.log for the error
2. Check EXECUTION-TRACKER.md for the blocker note
3. Fix the blocker and re-run the task manually

Re-run a single task:
\`\`\`bash
bash scripts/run_task.sh <TASK_ID>
\`\`\`
MORNING
fi)

## Task logs
$(for task in "${PASSED_TASKS[@]:-}" "${FAILED_TASKS[@]:-}"; do
    task_id="${task%%:*}"
    echo "- \`logs/tasks/${task_id}.log\`"
done)

## Full test output
\`\`\`
$(PYTHONPATH=. pytest -q 2>&1 | tail -20 || echo "pytest not run")
\`\`\`
REPORT

    log "Morning report written to: $REPORT"
}

# ── Task sequence ─────────────────────────────────────────────────────────────
# C1-INFRA is a prerequisite — must be done before running this script.
# This script runs C1-PARALLEL-1 tasks in dependency order.

main() {
    log "═══════════════════════════════════════════════════════════"
    log "  Engram v2 Overnight Build — $(date '+%A, %B %d %Y %H:%M')"
    log "═══════════════════════════════════════════════════════════"

    check_prereqs

    # Stage 1: Models (foundation — everything depends on this)
    run_task "C1-MODELS" \
        "PYTHONPATH=. pytest tests/unit/test_models.py -q" \
        || { write_report; exit 1; }

    log "Models complete. Launching services + jobs (both depend only on models)..."

    # Stage 2a: Core services (depends on models)
    run_task "C1-SERVICES-CORE" \
        "PYTHONPATH=. pytest tests/unit/test_lifecycle.py tests/integration/test_entities.py tests/integration/test_links.py -q" \
        || { write_report; exit 1; }

    # Stage 2b: Job worker (depends on models, parallel with services in theory — sequential here for safety)
    run_task "C1-JOBS" \
        "PYTHONPATH=. pytest tests/integration/test_jobs.py -q" \
        || { write_report; exit 1; }

    # Stage 2c: Search (depends on models)
    run_task "C1-SEARCH" \
        "PYTHONPATH=. pytest tests/integration/test_search_api.py -q" \
        || { write_report; exit 1; }

    # Stage 3: AI pipeline (depends on models + jobs)
    run_task "C1-AI-PIPELINE" \
        "PYTHONPATH=. pytest tests/unit/test_ai_pipeline.py tests/integration/test_ingestion.py -q" \
        || { write_report; exit 1; }

    # Stage 4: API layer (depends on all services)
    run_task "C1-API" \
        "PYTHONPATH=. pytest tests/integration/test_api_compat.py -q" \
        || { write_report; exit 1; }

    # Stage 5: Full validation
    log "━━━ C1-VALIDATE: Full suite ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if PYTHONPATH=. pytest -q --cov=. --cov-report=term-missing 2>&1 | tee "$TASK_LOG_DIR/C1-VALIDATE.log"; then
        ok "Full suite passed"
        PASSED_TASKS+=("C1-VALIDATE")
    else
        fail "Full suite FAILED"
        FAILED_TASKS+=("C1-VALIDATE")
    fi

    # Frontend build check
    log "Checking frontend build..."
    if cd ui && npm run build >> "$TASK_LOG_DIR/C1-VALIDATE.log" 2>&1; then
        ok "Frontend build passed"
        cd "$REPO_DIR"
    else
        warn "Frontend build failed — backend may still be usable"
        cd "$REPO_DIR"
    fi

    write_report

    if [ ${#FAILED_TASKS[@]} -eq 0 ]; then
        log ""
        ok "═══════════════════════════════════════════"
        ok "  ALL TASKS PASSED. Sleep well. 🎉"
        ok "═══════════════════════════════════════════"
    else
        fail "═════════════════════════════════════════"
        fail "  ${#FAILED_TASKS[@]} task(s) failed. See morning report."
        fail "═════════════════════════════════════════"
        exit 1
    fi
}

main "$@"
