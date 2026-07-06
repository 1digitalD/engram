# AGENTS.md - Engram v4

This file is the entry point for agents working in this repository. Read it before touching code.

## Project Purpose

Engram is a self-hosted personal workspace: capture anything, recall it later, and run projects and tasks with AI assistance. It is single-user and self-hosted.

The active implementation is Engram v4.

## Active Documentation

| Document | Purpose |
|---|---|
| `docs/V4_WORLD_MODEL_PLAN.md` | **Active implementation plan** (20 slices, Phases A–F) |
| `docs/V4_PRINCIPLES.md` | Non-negotiable v4 product and architecture rules |
| `docs/SCHEMA.sql` | Canonical v4 Postgres schema |
| `mcp_server/README_V4.md` | v4 MCP contract and tool surface |
| `docs/DEPLOY.md` | Local launchd + Tailscale deployment workflow (API `:5001`, MCP `:8765`) |
| `EXECUTION-TRACKER.md` | Fresh-agent handoff, current repo state, and archived milestones |

`docs/V4_IMPLEMENTATION_PLAN.md` is archived history. `prd.json` is archived reference only.
The current plan is `docs/V4_WORLD_MODEL_PLAN.md`.

## Non-Negotiable Rules

- `/api/v4` is the only target runtime API.
- Do not build compatibility adapters for old response shapes.
- Do not store relationship IDs inside `properties`.
- All relationships must use `EntityLink` / relationship records.
- Notes remain source artifacts. AI may extract from notes, never convert them.
- Safe metadata and high-confidence linking may be auto-applied with audit events.
- Risky creation, status, deletion, merge, and relationship-deletion work must be suggestions.
- MCP is write-enabled for v4 and must stay aligned with the active `/api/v4` contract.
- Work proceeds slice by slice (see `docs/V4_WORLD_MODEL_PLAN.md`) with validation before moving on.

## ⚠️ Production Data Safety (read before any schema or deploy work)

The production DB at `postgresql://engram:engram@localhost:5432/engram` contains real data.

- **Never run `flask init-db` against production** — it wipes all data.
- **Never set `DATABASE_URL` or `TEST_DATABASE_URL` to port 5432** in test contexts.
- **Always run `bash scripts/backup_prod.sh` before any schema change or deploy.**
- Schema changes must be additive-only, shipped as numbered scripts in `scripts/migrations/`.
- Tests run only against the isolated test DB (port 5433, `docker-compose.test.yml`).
- See `docs/V4_PRINCIPLES.md` → "Production Data Safety" for the full protocol.

## Working Rules

- Read the v4 principles and implementation plan before changing code.
- Keep changes simple, explicit, and testable.
- Write or update tests for behavior changes.
- Run focused validation first, then broader validation.
- Commit logical, reviewable units.
- Do not touch `.venv/`, `venv/`, `ui/node_modules/`, or ignored build artifacts.
- Do not revert unrelated user changes.

## Validation Commands

```bash
# Backend tests — always use TEST_DATABASE_URL pointing to port 5433
TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest -q
TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest tests/unit/ -q
TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest tests/integration/ -q

# Run backend pytest commands serially against the shared test DB.
# Do not run multiple pytest processes in parallel unless each process has its own isolated database.

# Frontend
cd ui && npm test
cd ui && npm run build

# Schema migration (additive only — never init-db on prod)
# Apply to test DB first: psql postgresql://engram:engram@localhost:5433/engram_test < scripts/migrations/NNN_name.sql
# Then prod (after backup): psql postgresql://engram:engram@localhost:5432/engram < scripts/migrations/NNN_name.sql

# Backup prod before any deploy
bash scripts/backup_prod.sh
```

## Conventions

- Backend: Flask + SQLAlchemy 2.x.
- Database: Postgres + pgvector using `docs/SCHEMA.sql`.
- **Never run `flask --app app.py init-db` against the production database** — it wipes all data.
- Frontend: React + Vite.
- Service layer owns business logic; API handlers should stay thin.
- Meaningful mutations write `entity_events`.
- AI actions use explicit `agent:*` actors and must not silently perform risky changes.
