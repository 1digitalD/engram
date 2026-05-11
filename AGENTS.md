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
- **SQLite files (`engram.db`) are the migration source**, not the runtime DB. After C1-INFRA completes, Postgres is the only DB.
- **OpenAI and Anthropic keys must be mocked in tests.** Never make real API calls in the test suite. See `tests/conftest.py` for `mock_openai` and `mock_embed` fixtures.
- **`tests/conftest.py` is shared.** Coordinate with other agents before modifying it.

---

## Archived (do not use for new work)

- `PLAN.md` — old phase plan, SQLite-based
- `SPEC.md` — old spec, superseded by `docs/PRD.md`
- `prd.json` — old task queue, inactive
- `AUDIT.md` — historical audit, for reference only
