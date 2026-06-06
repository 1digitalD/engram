# Engram — Execution Tracker

This file is the fresh-agent handoff for the current v4 baseline. Use it to reconstruct context quickly without reading stale task logs first.

Last updated: 2026-06-05
Branch: `main`
Runtime baseline: `/api/v4` only, fresh Postgres + pgvector schema, write-enabled MCP aligned with the active API.

## Active Sources Of Truth

Read these before changing code:

| Document | Purpose |
|---|---|
| `AGENTS.md` | Repo-wide working rules and active artifact list |
| `docs/V4_PRINCIPLES.md` | Non-negotiable product and architecture rules |
| `docs/V4_IMPLEMENTATION_PLAN.md` | Contract, endpoints, and acceptance criteria |
| `docs/SCHEMA.sql` | Canonical fresh schema |
| `mcp_server/README_V4.md` | MCP contract and transport |
| `docs/DEPLOY.md` | launchd + Tailscale deployment workflow |

Non-authoritative historical artifacts:

- `prd.json` is archived reference material only.
- Older V2/V3 execution history below is for archaeology, not planning.

## Current Baseline

- The only runtime API is `/api/v4`.
- MCP is write-enabled and must stay aligned with `/api/v4`.
- Relationship records use `EntityLink` only; relationship IDs must not appear in `properties`.
- `activity_update` is an allowed relationship type used for summary-context notes.
- `/api/v4/today` includes overdue work, follow-ups, blocked/waiting tasks, projects without open tasks, recent notes, and pending suggestions.
- Meaningful mutations must write `entity_events`.

## Validation Commands

```bash
PYTHONPATH=. ./venv/bin/pytest -q
PYTHONPATH=. ./venv/bin/pytest tests/unit/ -q
PYTHONPATH=. ./venv/bin/pytest tests/integration/ -q
cd ui && npm test
cd ui && npm run build
plutil -lint com.engram.api.plist
bash scripts/apply_schema.sh
```

Test environment note:

- Backend tests expect `TEST_DATABASE_URL` to point at the isolated Postgres test instance, typically `postgresql://engram:engram@localhost:5433/engram_test`.
- If tests fail with connection errors, start the test DB first with `docker compose -f docker-compose.test.yml up -d`.

## Startup And Deployment

Development:

```bash
docker compose up -d
flask --app app.py init-db
PORT=5001 flask --app app.py run
cd ui && npm install && npm run dev
```

Local launchd deployment:

- LaunchAgent: `com.engram.api.plist`
- Deploy helper: `scripts/engram-deploy.sh`
- Runbook: `docs/DEPLOY.md`

The launchd/Tailscale path expects the API to bind to `127.0.0.1:5001`.

## Recent Completed Milestones

- v4 API/runtime cutover is in place.
- Relationship API, Today, Suggestions, Search, Canonical markdown, MCP, and Activity Updates are implemented.
- Baseline cleanup aligned docs, runtime contracts, MCP scope, Today payload, and deployment artifacts.

## Archive Summary

The repo previously tracked fine-grained V2/V3/V3.5 execution logs in this file. Those logs were useful during active migration work but are now demoted because they contain stale pending-task guidance that can mislead fresh agents. Recover detailed history with `git log --oneline --decorate -- EXECUTION-TRACKER.md` if needed.
