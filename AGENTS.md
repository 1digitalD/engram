# AGENTS.md - Engram v4

This file is the entry point for agents working in this repository. Read it before touching code.

## Project Purpose

Engram is a self-hosted personal workspace: capture anything, recall it later, and run projects and tasks with AI assistance. It is single-user and self-hosted.

The active implementation is Engram v4. v4 is a fresh clean cutover.

## Active Documentation

| Document | Purpose |
|---|---|
| `docs/V4_PRINCIPLES.md` | Non-negotiable v4 product and architecture rules |
| `docs/V4_IMPLEMENTATION_PLAN.md` | v4 cycle plan and acceptance criteria |
| `docs/SCHEMA.sql` | Canonical fresh v4 Postgres schema |
| `mcp_server/README_V4.md` | v4 MCP tools (read + write) |
| `EXECUTION-TRACKER.md` | Historical and current execution log |

Historical plans and PRDs are not active sources of truth for v4 work.

## Non-Negotiable v4 Rules

- Do not preserve backward compatibility.
- Do not implement migration.
- Existing local app data can be deleted.
- Do not preserve `/api/v1` or `/api/v2` behavior.
- `/api/v4` is the only target runtime API.
- Do not build compatibility adapters for old response shapes.
- Do not store relationship IDs inside `properties`.
- All relationships must use `EntityLink` / relationship records.
- Notes remain source artifacts.
- AI can extract from notes, but must not convert notes into other entity types.
- Safe metadata and high-confidence linking may be auto-applied.
- Risky creation, status, deletion, merge, and relationship-deletion work must be suggestions.
- Work proceeds cycle by cycle with validation before moving on.

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
PYTHONPATH=. ./venv/bin/pytest -q
PYTHONPATH=. ./venv/bin/pytest tests/unit/ -q
PYTHONPATH=. ./venv/bin/pytest tests/integration/ -q
cd ui && npm test
cd ui && npm run build
bash scripts/apply_schema.sh
```

## Conventions

- Backend: Flask + SQLAlchemy 2.x.
- Database: fresh Postgres + pgvector using `docs/SCHEMA.sql`.
- `flask --app app.py init-db` is destructive by default and resets local app tables for the v4 clean cutover.
- Frontend: React + Vite.
- Service layer owns business logic; API handlers should stay thin.
- Meaningful mutations write `entity_events`.
- AI actions use explicit `agent:*` actors and must not silently perform risky changes.
