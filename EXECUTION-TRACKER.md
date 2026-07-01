# Engram — Execution Tracker

Fresh-agent handoff for the current v4 baseline. Use this to get oriented quickly,
then read the active source docs before changing code.

Last updated: 2026-07-01
Branch: `main`
Status: deploy/doc cleanup aligned to the current runtime; deploy smoke now checks
the live `/now`, `/threads`, and `/memory` data paths through their backing `/api/v4`
endpoints.

Runtime baseline: `/api/v4` only, fresh Postgres + pgvector schema, write-enabled MCP
aligned with the active API.

## Current hardening loop: Iteration 17 (2026-07-01)

- Loopsmith runtime fully drained end-of-v5 Phase 3 work, with a new execution overlay
  created in `prd.json` for post-Phase-3 hardening slices.
- That overlay is intentionally narrower than the repo planning source of truth:
  `docs/V4_WORLD_MODEL_PLAN.md` remains the active implementation plan.
- Current hardening order: loop reliability, truthful UI state, Recall hardening,
  `New` semantics, and smoke coverage.
- `loopsmithctl doctor --strict` is not hanging indefinitely; it is exceeding the
  orchestrator timeout because strict probes currently take about 41 seconds and the
  Codex executor blocks on stdin during the strict probe.

### Validation findings retained from the current loop

- `TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest tests/unit/ -q`
  previously passed: **171 passed**.
- `TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest tests/integration/test_v4_ask.py -q`
  previously passed with **4 passed, 2 pre-existing failures** unrelated to deploy/docs.
- Full backend suite previously sat at **377 passed, 6 failed**, with the known failures in:
  `tests/integration/test_v4_ask.py`, `tests/integration/test_v4_search.py`, and
  `tests/integration/test_v4_today.py`.

## Latest slice: hardening-interaction-smoke (2026-07-01)

- Added focused frontend interaction coverage for capture retry, Ask, Recall, and
  entity-list creation entry points.
- Focused frontend tests previously passed:
  `cd ui && npm test -- V5CaptureSheet V5AskSheet V5Recall V5EntityList`
- Full frontend suite previously passed:
  `cd ui && npm test`
- Frontend build previously passed:
  `cd ui && npm run build`

## Latest deploy/doc cleanup (2026-07-01)

- `scripts/engram-deploy.sh` now treats deploy success as more than a bare health check.
- Post-restart smoke is read-only and covers:
  `GET /api/v4/health`, `GET /api/v4/summary`, `GET /api/v4/today`,
  `GET /api/v4/threads?rank=attention&limit=1`, and `GET /api/v4/timeline?limit=1`.
- `docs/DEPLOY.md` now matches the current runtime routing model:
  `/` redirects to `/now`, with `/threads`, `/memory`, and `/recall` as the primary
  top-level lenses.
- `/api/v4/inbox` still exists as backend review data, but it should not be treated as
  the primary app landing route in current docs.

## Active Sources of Truth

Read these before changing code:

| Document | Purpose |
|---|---|
| `AGENTS.md` | Repo-wide working rules and active artifact list |
| `docs/V4_PRINCIPLES.md` | Non-negotiable product and architecture rules |
| `docs/V4_WORLD_MODEL_PLAN.md` | Active implementation plan and slice order |
| `docs/SCHEMA.sql` | Canonical fresh schema |
| `mcp_server/README_V4.md` | MCP contract and transport |
| `docs/DEPLOY.md` | launchd + Tailscale deployment workflow |

Non-authoritative historical artifacts:

- `prd.json` is archived reference material only.
- Older V2/V3 execution history is archaeology, not planning input.
- If route history or older UI milestone details matter, use `docs/iterations/` and git
  history instead of older tracker snapshots.

## Current Baseline

- The only runtime API is `/api/v4`.
- MCP is write-enabled and must stay aligned with `/api/v4`.
- Relationship records use `EntityLink` only; relationship IDs must not appear in
  `properties`.
- `activity_update` is an allowed relationship type used for summary-context notes.
- `/api/v4/today` includes overdue work, follow-ups, blocked/waiting tasks, projects
  without open tasks, recent notes, pending suggestions, and derived attention buckets.
- `/api/v4/summary` returns counts used by the shell plus coordination radar.
- Meaningful mutations write `entity_events`.

## Current Runtime Surfaces

- `/` redirects to `/now`.
- Primary top-level app routes are `/now`, `/threads`, `/memory`, and `/recall`.
- Entity collection routes remain `/notes`, `/projects`, `/tasks`, `/areas`, `/people`,
  and `/resources`, with detail routes under each collection plus `/entities/:id`.
- `/api/v4/inbox` still exists as a backend review/feed endpoint, but it is not the
  current top-level UI landing route.

## Deploy + Validation Baseline

- Production launch path is `scripts/engram-deploy.sh` plus
  `~/Library/LaunchAgents/com.engram.api.plist`.
- Every deploy must run `bash scripts/backup_prod.sh` before restart work touches
  production.
- The deploy script now performs a focused read-only smoke after restart:
  `GET /api/v4/health`, `GET /api/v4/summary`, `GET /api/v4/today`,
  `GET /api/v4/threads?rank=attention&limit=1`, and `GET /api/v4/timeline?limit=1`.
- Treat a failed smoke as a failed deploy even if the process is technically listening
  on port `5001`.

## Active Delivery Method

- Reusable process artifact: `docs/playbooks/SOFTWARE_DELIVERY_PLAYBOOK.md`
- Iteration planning template: `docs/templates/ITERATION_CONTRACT_TEMPLATE.md`
- This tracker remains the continuity artifact for current execution state.
- Keep process minimal: use only the playbook, template, and tracker unless the work
  proves more structure is needed.
