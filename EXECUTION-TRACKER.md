# Engram — Execution Tracker

This file is the fresh-agent handoff for the current v4 baseline. Use it to reconstruct context quickly without reading stale task logs first.

Last updated: 2026-06-06
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

## Active Delivery Method

- Reusable process artifact: `docs/playbooks/SOFTWARE_DELIVERY_PLAYBOOK.md`
- Iteration planning template: `docs/templates/ITERATION_CONTRACT_TEMPLATE.md`
- This tracker remains the continuity artifact for current execution state.
- Keep process minimal: use only the playbook, the template, and this tracker unless the work proves more structure is needed.

## Active UI Improvement Direction

- Product goal: evolve the v4 UI into a more intuitive control plane, planner, organizer, and capture/review surface without drifting from the active v4 principles.
- Delivery mode: small vertical slices with end-to-end verification before moving to the next slice.
- Current recommendation order:
  1. Interaction Consistency Pass
  2. Control Plane Home
  3. Review Queue
  4. Global Capture Surface
  5. Planner Upgrade
  6. Project Workspace
  7. Inspection + Trust
  8. Task Workspace
  9. Area Workspace
  10. Person Workspace
  11. Resource Workspace
  12. Today Review Navigation
  13. Detail Return Navigation
- Active iteration contract: `docs/iterations/ITERATION_13_DETAIL_RETURN_NAV.md`
- Iteration 0 implementation status:
  - entity detail save semantics were changed to an explicit-save model
  - sidebar `Today` count now uses the same actionable buckets as the `Today` screen
  - focused and full frontend tests passed
  - frontend build passed
  - manual visual QA on the live app is still recommended
- Iteration 1 implementation status:
  - `/` now renders a control-plane Home route
  - Inbox remains intact at `/inbox`
  - Home is assembled only from existing `inbox`, `today`, and `entities.list(project)` payloads
  - focused and full frontend tests passed
  - frontend build passed
  - manual visual QA on the live app is still recommended
- Immediate next step: implement Iteration 2 by grouping suggestion review around source notes and reducing the hops between Inbox and review work.
- Iteration 2 implementation status:
  - suggestions are now grouped around source notes where possible
  - review cards show source-note context and support per-group batch actions
  - focused and full frontend tests passed
  - frontend build passed
  - manual visual QA on the live app is still recommended
- Iteration 3 implementation status:
  - a persistent global quick action surface is now available across app routes
  - users can capture a note or create a task/project without returning to Inbox or list screens
  - search is directly reachable from the shell
  - focused and full frontend tests passed
  - frontend build passed
  - manual visual QA on the live app is still recommended
- Iteration 4 implementation status:
  - Today now includes a derived `Focus now` section assembled from existing urgency buckets
  - task and queue rows now show concise reason labels such as overdue, due today, follow-up, blocked, and waiting
  - a compact summary strip gives scan-level planning context without introducing stored planner state
  - actionable counts are deduped across overlapping today buckets
  - sidebar inbox count now reflects the real review queue instead of a truncated note count
  - focused and full frontend tests passed
  - frontend build passed
  - live manual QA on the local app is the next recommended check
- Iteration 5 implementation status:
  - project detail now includes a project-only workspace overview built from existing detail sections
  - the workspace surfaces open/completed task counts, people, notes, resources, and the next actionable task
  - obvious project hygiene gaps are now called out directly on the page
  - focused and full frontend tests passed
  - frontend build passed
  - live manual QA on a populated project detail is still recommended
- Iteration 6 implementation status:
  - entity detail now includes a compact inspection panel powered by existing detail and event history endpoints
  - the panel surfaces AI status/confidence, source, timestamps, and recent entity events without leaving the page
  - suggestion review now shows explicit confidence and note-level provenance context before risky accept/dismiss actions
  - live QA tightened the inspection panel by filtering low-signal duplicate history rows and reducing dead space in the trust surface
  - zero-confidence provenance is now hidden so trust cues only show meaningful scores
  - focused and full frontend tests passed
  - frontend build passed
  - live QA was run on task detail, note detail, and Suggestions; project detail is still worth a quick visual pass on populated data
- Iteration 7 implementation status:
  - note detail now includes a note-only workspace overview built from existing detail sections plus the pending suggestions list
  - the workspace surfaces linked extraction outcomes and whether review is still pending for the source note
  - notes with pending suggestions now provide a direct path back to the Suggestions review flow
  - focused and full frontend tests passed
  - frontend build passed
  - live QA for the new note workspace is still recommended on populated notes with and without pending suggestions
- Iteration 8 implementation status:
  - task detail now includes a task-only workspace overview built from existing task detail sections
  - the workspace surfaces ownership, scope, supporting context, and execution watchouts without new backend shape
  - activity updates remain directly below the main detail panel, with task workspace context beneath them
  - focused frontend tests passed
  - full frontend tests passed
  - frontend build passed
- Iteration 9 implementation status:
  - area detail now includes an area-only workspace overview built from existing detail sections
  - the workspace surfaces active projects, rolled-up open work, coverage, and stewardship watchouts without new backend shape
  - activity updates remain directly below the main detail panel, with area workspace context beneath them
  - focused frontend tests passed
  - full frontend tests passed
  - frontend build passed
  - live QA suggests a follow-up check is still needed on `/areas`, where the in-app browser list view did not match the API payload on the same host
- Iteration 10 implementation status:
  - person detail now includes a person-only workspace overview built from existing detail sections
  - the workspace surfaces current load, linked context, and coordination watchouts without new backend shape
  - focused frontend tests passed
  - full frontend tests passed
  - frontend build passed
- Iteration 11 implementation status:
  - resource detail now includes a resource-only workspace overview built from existing detail sections
  - the workspace surfaces primary anchor context, coverage, and adoption watchouts without new backend shape
  - focused frontend tests passed
  - full frontend tests passed
  - frontend build passed
- Iteration 12 implementation status:
  - Today now groups pending suggestions around source notes where possible instead of rendering flat generic review rows
  - Today provides direct paths to open the source note and to continue in the Suggestions review queue
  - focused frontend tests passed
  - full frontend tests passed
  - frontend build passed
- Iteration 13 implementation status:
  - entity detail now surfaces a contextual back action that prefers the originating route when present
  - the action falls back to the entity collection route when no source route is available
  - focused frontend tests passed
  - full frontend tests passed
  - frontend build passed
- Immediate next step: continue navigation/review polish or return to the unresolved `/areas` runtime inconsistency.

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
