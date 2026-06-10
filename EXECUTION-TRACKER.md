# Engram — Execution Tracker

This file is the fresh-agent handoff for the current v4 baseline. Use it to reconstruct context quickly without reading stale task logs first.

Last updated: 2026-06-07
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
  14. List Loading State
  15. UI Stabilization
  16. Final UI Refinement
- Active iteration contract: `docs/iterations/ITERATION_16_FINAL_UI_REFINEMENT.md`
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
- Iteration 14 implementation status:
  - entity list screens now show an explicit loading state instead of rendering false empty-state copy during the initial fetch
  - create loading and list-fetch loading are now tracked separately so create flows remain unaffected
  - focused frontend tests passed
  - full frontend tests passed
  - frontend build passed
- Iteration 15 implementation status:
  - route-level screens now size against the shell viewport instead of assuming full-window height
  - the shell quick-action bar is now home-only, removing duplicate top-bar controls from inbox and entity routes
  - entity list state now resets correctly when switching types through sidebar navigation on the shared mounted list view
  - inbox cards were simplified to avoid nested-link and segment-overlap issues
  - entity detail scroll was restored by making the route viewport a flex column and the shared entity screen a real flex child scroll container
  - simple archive-driven entity types now hide the redundant lifecycle control and promote archived filtering automatically through the status rail
  - focused frontend tests passed
  - full frontend tests passed
  - frontend build passed
- Iteration 16 implementation status:
  - entity detail now uses a constrained reading/edit column inside the main detail panel so dense editing surfaces read more cleanly
  - mobile shell navigation now uses grouped horizontal rails instead of wrapped sidebar links
  - shared entity/detail surfaces now compress more deliberately under mobile breakpoints
  - Home now acts more clearly as the control plane, while Inbox is framed as the capture/review lane
  - Home no longer duplicates recent note browsing with another note list and instead routes users into Inbox, Suggestions, and Notes intentionally
  - focused frontend tests passed
  - full frontend tests and frontend build are the final validation step for this slice
- Immediate next step: if validation passes, shift primary delivery focus from frontend structure to agentic/backend improvements, with only targeted UI follow-ups as bugs or validation findings demand.
- Slice B1 (`progress_update` reconciliation action) implementation status:
  - reconciler can return `action: "progress_update"` with `target_id` + `update_text`; `SYSTEM_PROMPT` documents it
  - capture auto-applies these: creates an activity-update note linked to the target, writes an `EntityEvent`, and surfaces it in `GET /entities/<id>/activity_updates`
  - `progress_update` decisions never become suggestions and never create new project/task entities; a hallucinated/missing `target_id` is skipped (not a fall-through to "new")
  - factored `_create_activity_update_note` helper out of the `POST /entities/<id>/activity_updates` route so capture and the route share dedup/cap logic
  - red-first integration tests added (`tests/integration/test_v4_capture_extraction.py`), full suite green: 192 passed (was 189)
  - replay eval run 3x post-change: 17/27, 17/27, 16/27 — below the single Phase A baseline reading (19/27) but the wrong items are dominated by pre-existing umbrella-area/Hemant matching noise documented in `SLICE_B1_UMBRELLA_LINK_FILTER.md`, not by `progress_update`; see `docs/iterations/SLICE_B1_PROGRESS_UPDATE.md` for full analysis
  - acceptance target "≥3 activity updates from one real standup note" verified at the mechanism level via integration tests; live model picked `progress_update` only 1-2x per 27-candidate eval run — follow-up prompt tuning needed to increase pickup rate
- Slice B2 (auto-apply state changes carried by `progress_update`) implementation status:
  - `progress_update` decisions can carry an optional `fields.status`; `SYSTEM_PROMPT` documents when to use it (shipped/delivered → done, waiting on X → waiting, blocked on X → blocked)
  - at confidence ≥ `AUTO_APPLY_CONFIDENCE` (0.8) and a status valid for the target's type and different from current, the status is auto-applied with an `ai_updated` `EntityEvent` recording `old_value`/`new_value`
  - below the gate, the status change becomes an `update_entity` suggestion (reuses existing `_accept_update_entity_suggestion`); the activity-update note is still applied either way (additive/safe per B1)
  - invalid/unchanged statuses are silently ignored (vocabulary guard via `VALID_STATUS`)
  - red-first integration tests added, full suite green: 195 passed (was 192)
  - replay eval run once post-change: 15/27 — consistent with the same pre-existing umbrella-area/person-matching noise as B1's runs (17/27, 17/27, 16/27), not caused by this slice's status logic (which fired on 0 status-bearing decisions in this run); see `docs/iterations/SLICE_B2_STATUS_AUTO_APPLY.md`
- Slice B3 (capture changelog + one-click undo) implementation status — **Phase B complete**:
  - additive schema: `entity_events.source_note_id` (FK → entities, links an event back to the capturing note) and `entity_events.reverted_at`, plus new `event_type` value `'reverted'`; `docs/SCHEMA.sql` updated and `scripts/migrations/001_add_event_revert_fields.sql` added for prod (not yet applied)
  - every `agent:v4-capture` `EntityEvent` written during capture now stamps `source_note_id`; `_apply_entity_update`'s `ai_updated` event now also records `old_value` (previously only `new_value`, which made it un-revertible)
  - new `GET /api/v4/entities/<id>/capture-changes` lists an note's agent-applied changes (`created`, `ai_updated`, `relationship_added`, `activity_update_added`)
  - new `POST /api/v4/events/<id>/revert` inverts a single change (status/title/due_at/follow_up_at restore, link removal, activity-update archival, created-entity → lifecycle deleted), itself logs a `reverted` EntityEvent, 409 on double-revert, 404 on unknown event
  - frontend: `CaptureChangesPanel` ("What the agent did") on note detail with per-row Revert
  - red-first integration tests (6 new) + 1 new UI test; full backend suite green: 201 passed (was 195); UI: 43 passed (was 42), build green
  - no extraction/reconciliation changes in this slice, so replay eval not re-run
  - **Phase B deployed to prod (2026-06-09)**: pre-migration snapshot taken (`backups/engram_prod_pre_b3_20260609_225003.dump`), `scripts/migrations/001_add_event_revert_fields.sql` applied to prod Postgres (additive only), `./scripts/engram-deploy.sh` run, `/api/v4/health` and `/api/v4/today` smoke-tested OK
- Slice C1 (delegation detection + cadence) implementation status:
  - new additive `app_settings` key/value table (`docs/SCHEMA.sql` + `scripts/migrations/002_add_app_settings.sql`, not yet applied to prod) holds owner aliases (`default: ["dan"]`) and per-person cadence overrides; defaults apply with no rows present
  - `_apply_assignee` now sets `follow_up_at = now + cadence working days` (default 3) on a task when assigned to a non-owner person and no `follow_up_at` is already set, recording an `ai_updated` event; covers capture and suggestion-accept paths
  - `_create_activity_update_note` now calls `_refresh_delegation_cadence`, pushing a delegated task's `follow_up_at` forward by the cadence again on each activity update
  - red-first integration tests (3 new) + `V4_TABLES` unit-test update; full suite green: 204 passed (was 201)
  - see `docs/iterations/SLICE_C1_DELEGATION_CADENCE.md`; not yet deployed (Phase C deploys once after C4)
- Slice C2 ("gone quiet" surfacing in /today) implementation status:
  - `GET /api/v4/today` gains `delegations_quiet`: tasks delegated to a non-owner person whose `follow_up_at` has passed with no activity update since, each annotated with `days_silent` and `last_update` preview; computed via new `_delegations_quiet(now)` helper with two batched queries (no N+1)
  - Today UI gains a "Delegations needing a nudge" section (hidden when empty)
  - red-first integration tests (2 new) + 1 UI test; full backend suite green: 206 passed (was 204); UI 43 passed, build green; live QA against prod confirms correct (empty) rendering
  - see `docs/iterations/SLICE_C2_GONE_QUIET.md`; not yet deployed (Phase C deploys once after C4)
- Slice C3 (person workspace: load + last-heard) implementation status:
  - `GET /api/v4/entities/<id>/detail` gains `current_load` for `person` entities: each open assigned task plus `last_heard_at`/`last_heard_preview` from its most recent activity-update note, via new `_person_current_load(person)` helper
  - refactored `_latest_activity_updates(entity_ids)` out of C2's `_delegations_quiet` so both features share the same batched (no N+1) lookup
  - `PersonWorkspacePanel`'s "Current load" card now lists all of `current_load` (was a single primary-task pointer), each with status/priority and a "Last heard ..." or "No activity update yet" line
  - red-first integration test added; full backend suite green: 207 passed (was 206); UI 43 passed, build green
  - see `docs/iterations/SLICE_C3_PERSON_LOAD.md`; not yet deployed (Phase C deploys once after C4)

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
