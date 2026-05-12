# AGENTS.md — Engram v2

> This file is the entry point for all agents. Read it fully before touching any code.

---

## Project purpose

Engram is a self-hosted personal workspace: capture anything, recall it later, run projects and tasks with AI assistance. Single user. Self-hosted on Mac Mini.

**The system is being rebuilt on a new architecture.** The old PLAN.md, SPEC.md, and prd.json reflect the previous direction and are archived for reference only. All active work uses the docs below.

---

## Active documentation (read before starting any task)

| Document | Purpose |
|---|---|
| `docs/PRD.md` | Product vision, entity model, lifecycle model, cycle goals |
| `docs/TECH_SPEC.md` | Stack, architecture, service contracts, migration mapping |
| `docs/SCHEMA.sql` | Canonical Postgres schema — source of truth for all DB structure |
| `docs/API_SPEC.md` | All API routes, request/response shapes, backward-compat rules |
| `docs/TEST_STRATEGY.md` | TDD approach, conftest fixtures, test patterns, CI config |
| `docs/AGENT_PLAN.md` | Task breakdown by cycle, file ownership map, done criteria |

---

## Working rules

- **Read your task's spec before writing a single line of code.** Each task in `docs/AGENT_PLAN.md` lists exactly what to read.
- **Write tests first.** Confirm they fail. Then implement. Confirm they pass. This is not optional.
- **Respect file ownership.** Each task owns specific files. Do not touch files outside your task's `writes` list. See the ownership map in `docs/AGENT_PLAN.md`.
- **A task is done only when its tests pass** and the full suite still passes. Report test output and coverage.
- **Update `EXECUTION-TRACKER.md`** after each completed or blocked task.
- **Commit logical, reviewable units.** One commit per task, or per meaningful sub-step within a task.
- **Do not touch `.venv/`** — leave it alone, do not commit it.

---

## Validation commands

```bash
# Full backend test suite
PYTHONPATH=. pytest -q --cov=. --cov-report=term-missing

# Unit tests only (fastest, no DB needed)
PYTHONPATH=. pytest tests/unit/ -q

# Integration tests (requires Postgres running)
PYTHONPATH=. pytest tests/integration/ -q

# Frontend build
cd ui && npm install && npm run build

# Apply schema to test DB
psql $TEST_DATABASE_URL -f docs/SCHEMA.sql
```

---

## Conventions

- Backend: Flask + SQLAlchemy 2.x. Migration scripts in `scripts/`, not Alembic.
- Frontend: React 18 + Vite + Zustand store at `ui/src/stores/useStore.js`.
- All DB structure changes go through `docs/SCHEMA.sql` first, then implementation. Never add columns in application code without updating the schema file.
- Service layer is the only place with business logic. API handlers call services only.
- All AI actions write to `entity_events` with `actor='agent:<name>'`. No silent mutations.

---

## Gotchas

- **Postgres requires pgvector extension.** Use `docker compose up -d` which uses `pgvector/pgvector:pg16` image.
- **`ui/node_modules` is not tracked.** Run `npm install` before `npm run build`.
- **OpenAI and Anthropic keys must be mocked in tests.** Never make real API calls in the test suite. See `tests/conftest.py` for `mock_openai` and `mock_embed` fixtures.
- **`tests/conftest.py` is shared.** Coordinate with other agents before modifying it.

---

## Rate limits and model selection

This project runs via an automated coding loop (`scripts/build_overnight.sh`) that
spawns one `claude --print` session per task. Each session makes many tool calls
(file reads, test runs, edits). To avoid hitting Anthropic API rate limits:

**Model defaults**

| Task | Recommended model | Why |
|---|---|---|
| C1-MODELS, C1-SERVICES-CORE, C1-AI-PIPELINE, C1-API | `claude-sonnet-4-6` | Multi-file rewrites, complex logic |
| C1-JOBS, C1-SEARCH, C2-* single-file tasks | `claude-haiku-4-5-20251001` | Simpler scope, 10× cheaper, faster |
| C1-INFRA (migration script), C3-* | `claude-sonnet-4-6` | Judgment-heavy |

Override per run: `CLAUDE_MODEL=claude-haiku-4-5-20251001 bash scripts/run_task.sh C1-JOBS`

**Pacing**

- `build_overnight.sh` sleeps `$INTER_TASK_SLEEP` seconds (default 90) between tasks.
- Override: `INTER_TASK_SLEEP=120 bash scripts/build_overnight.sh`
- Skip for rapid local iteration: `SKIP_SLEEP=1 bash scripts/build_overnight.sh`
- The script retries a failed `claude` invocation up to `$CLAUDE_MAX_RETRIES` times
  (default 3) with exponential backoff starting at 60s (60 → 120 → 240).

**If you hit rate limits mid-task**

1. Check `logs/tasks/<task_id>.log` — the agent writes partial progress before exiting.
2. Check `EXECUTION-TRACKER.md` for any blocker the agent recorded.
3. Wait 5–10 minutes, then re-run: `bash scripts/run_task.sh <TASK_ID>`
4. The agent will re-read the spec and pick up from where the code is — it does not
   resume a session, so ensure any partial file writes are valid Python/JS before re-running.

---

## Archived (do not use for new work)

- `archive/PLAN.md` — old phase plan, archived
- `archive/SPEC.md` — old spec, superseded by `docs/PRD.md`
- `archive/prd.json` — old task queue, inactive
- `archive/v1-prd-before-v2-bootstrap.json` — old v1 executable queue, archived 2026-05-11 when `prd.json` was re-bootstrapped for v2 Cycle 1
- `archive/AUDIT.md` — historical audit, for reference only
