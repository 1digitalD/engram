# Engram — Execution Tracker

This file is the fresh-agent handoff for the current v4 baseline. Use it to reconstruct context quickly without reading stale task logs first.

Last updated: 2026-06-30
Branch: `main`
Runtime baseline: `/api/v4` only, fresh Postgres + pgvector schema, write-enabled MCP aligned with the active API.

## Latest slice: prd-timeline (2026-06-30)

- Added `GET /api/v4/timeline` with chronological event stream, filtering, pagination, narration, and derived `thread_id`.
- Added migration `scripts/migrations/005_timeline_index.sql` and updated `docs/SCHEMA.sql` with `(created_at DESC)` index.
- Added V5Memory view at `/memory` with date-grouped timeline, entity-type/actor/thread filters, search, infinite scroll, and mobile pull-to-refresh.
- Integration tests: `tests/integration/test_v4_timeline.py` (8/8 passing with `test_v4_entity_detail.py`).
- UI tests and build pass.

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
- Slice C4 (blocks links from updates) implementation status:
  - reconciler `progress_update` decisions can carry `blocked_by_id`; `SYSTEM_PROMPT` documents when to set it (status becomes blocked/waiting and a specific blocker entity is named)
  - new `_creates_blocks_cycle(source_id, target_id)` (BFS over existing `blocks` links); `_create_entity_link` refuses cyclic `blocks` links, and the manual `POST /entities/<id>/relationships` and `PATCH /relationships/<id>` paths return 409 "relationship would create a blocks cycle"
  - high-confidence `progress_update` status auto-apply to blocked/waiting now also creates a `blocks` link (blocker → target) when `blocked_by_id` resolves to an existing, non-cyclic entity, with an `applied_changes` entry and `relationship_added` `EntityEvent`
  - red-first integration tests (3 new); full suite green: 210 passed (was 207)
  - see `docs/iterations/SLICE_C4_BLOCKS_LINKS.md`
  - **Phase C deployed to prod (2026-06-10)**: pre-migration snapshot taken (`backups/engram_prod_pre_phasec_20260610_065610.dump`), `scripts/migrations/002_add_app_settings.sql` applied to prod Postgres (additive only, defaults apply with no rows present), `./scripts/engram-deploy.sh` run, `/api/v4/health` and `/api/v4/today` (including new `delegations_quiet`) smoke-tested OK

## Phase D

- Slice D1 (project priority, inherited by tasks) implementation status:
  - `attention_for_entity` gains `inherited_priority`; effective priority is `own or inherited`, with `priority:<level>` reason labeled "(from project)" when inherited; function stays pure (no DB queries)
  - new `_inherited_task_priorities(tasks)` (one batched query); `_entity_with_attention` threads `inherited_priority` through and adds `inherited_priority` to the entity dict when used
  - `GET /api/v4/today` computes inherited priorities once across all task buckets and applies them via a `with_priority` closure
  - Today UI shows a `~<priority>` pill ("Inherited from project") when an item has no own priority but an inherited one
  - new read-only `scripts/list_project_priorities.py` lists active projects + priority for Dan's bulk-review (priority itself is already editable per-entity via the existing generic priority control, so no new UI control was needed)
  - red-first tests (2 unit + 1 integration); full backend suite green: 213 passed (was 210); UI 43 passed, build green; live QA against prod confirms no regressions (no prod project has a priority set yet, so no `~<priority>` pill renders)
  - see `docs/iterations/SLICE_D1_PROJECT_PRIORITY_INHERITANCE.md`; deployed with Phase D (2026-06-10)

- Slice D2 (priority escalation from capture) implementation status:
  - `_accept_update_entity_suggestion` now supports `fields.priority`, validating against `low|medium|high|urgent` and writing to `target_entity.properties.priority` (recorded via the existing `updated` event)
  - reconciliation `SYSTEM_PROMPT` for `progress_update` now also accepts `fields.priority`, populated only when the update text uses explicit escalation language (not inferred from routine status updates)
  - in `_apply_reconciliation_decision`'s `progress_update` branch, when escalation implies a priority strictly higher than the target's current `properties.priority`, a `change_priority`-style `update_entity` suggestion (`payload.fields={"priority": "<level>"}`) is always created via `_append_capture_suggestion` — never auto-applied regardless of confidence
  - red-first tests: 2 integration (`test_v4_suggestions.py` accept w/ valid + invalid priority), 2 integration (`test_v4_capture_extraction.py` escalation creates suggestion; non-escalating priority is ignored); full backend suite green: 217 passed (was 213)
  - see `docs/iterations/SLICE_D2_PRIORITY_ESCALATION.md`; deployed with Phase D (2026-06-10)

- Slice D3 (server-side attention v2: impact + staleness) implementation status:
  - `attention_for_entity` gains `staleness_days` (weighted via a tiered table: ≥21d→25, ≥14d→18, ≥7d→10, ≥3d→4) and `blocks_count` (weighted `min(24, count*12)`); both are pure inputs computed by the caller, no DB access inside the function
  - new batched helpers `_staleness_days_for(entities, now)` (last activity-update, falling back to `created_at`) and `_blocking_impact_counts(entities)` (active non-done entities blocked via `blocks` links)
  - `GET /api/v4/today` now also queries undated/unscheduled open tasks (`due_at` and `follow_up_at` both null), scores them via impact+staleness, and returns the top 20 with score > 0 as a new `unscheduled_attention_tasks` bucket; staleness/impact are also threaded into all other task buckets
  - Today UI: new "Needs attention (no date set)" section renders `unscheduled_attention_tasks`; `getTodayAttentionCount` includes them in the daily total (focus-now ranking left unchanged to avoid displacing existing high-signal items)
  - red-first tests: 3 unit (staleness table, impact table, undated-high-priority-stale-task outranks dated-low-priority-task per spec) + 1 integration (`/today` surfaces stale + blocking undated tasks, excludes quiet ones); full backend suite green: 221 passed (was 217); UI 43 passed, build green; live-checked against prod `/today` on a scratch port (20 unscheduled tasks surfaced correctly, then torn down)
  - see `docs/iterations/SLICE_D3_ATTENTION_V2.md`; deployed with Phase D (2026-06-10)

- Slice D4 (Today restructure + day reviewed) implementation status:
  - `GET /api/v4/today` gains a new `upcoming_due_tasks` bucket (due_at in (today, end of week]), threaded through the same staleness/impact/priority pipeline as the other task buckets
  - new `_set_app_setting(key, value)` helper (upsert into existing `app_settings` table); `/today` returns `last_reviewed_at` and `reviewed_today` (true iff the stored timestamp is on/after the start of today UTC)
  - new `POST /api/v4/today/review` writes `app_settings.last_reviewed_at = now()` and returns the same `last_reviewed_at`/`reviewed_today` shape
  - Today UI regrouped per spec: "Overdue"/"Due today" stay on top; overdue follow-ups, follow-ups, blocked, waiting, and unscheduled-attention tasks are merged into one "Your actions" section (each item keeps its original reason pill); "Delegations needing a nudge" unchanged; new collapsed "Deadlines ahead" section combines `upcoming_follow_ups` + `upcoming_due_tasks`; new "Mark day reviewed" button in the header calls the new endpoint and disables itself once `reviewed_today` is true
  - red-first tests: 2 new integration tests (`upcoming_due_tasks` bucket excludes overdue/due-today; day-reviewed flow incl. midnight reset via backdated `app_settings` row); full backend suite green: 223 passed (was 221); UI 43 passed, build green; live-checked against prod `/today` on the dev server (read-only — did not click "Mark day reviewed" since it proxies to the live prod DB)
  - see `docs/iterations/SLICE_D4_TODAY_RESTRUCTURE.md`
  - **Phase D deployed to prod (2026-06-10)**: pre-deploy snapshot taken (`backups/engram_prod_pre_phased_20260610_093236.dump`, no new migration needed — `app_settings` already present from Phase C), `./scripts/engram-deploy.sh` run, `/api/v4/health` and `/api/v4/today` smoke-tested OK (new `upcoming_due_tasks`/`last_reviewed_at`/`reviewed_today` fields present and correct)

- Slice E1 (`/api/v4/summary` + sidebar counts) implementation status:
  - new `services/v4_attention.today_attention_count(today_payload)` — pure port of the JS `getTodayAttentionCount` dedupe logic (overdue/due-today/follow-up/blocked/waiting/high-signal-note/unscheduled buckets, deduped by entity id)
  - `today()` refactored into `_build_today_payload(now)` (same JSON contract); `/inbox`'s "needs review" filter extracted into `_needs_review_query()`/`_needs_review_count()`, shared with the new endpoint
  - new `GET /api/v4/summary` returns `{inbox_count, today_count, suggestions_count, last_reviewed_at, reviewed_today}` in one call
  - `ui/src/api/v4Client.js` gains `v4API.summary()`; `App.jsx`'s `useSidebarCounts` now makes one `/summary` call instead of three (`/inbox`, `/today`, `/suggestions`)
  - red-first tests: 2 new unit tests (dedupe-across-buckets parity, empty-payload) + 1 new integration test (`/summary` counts match `/today`+`/inbox` via the same Python dedupe function); full backend suite green: 226 passed (was 223); UI 43 passed, build green
  - see `docs/iterations/SLICE_E1_SUMMARY_ENDPOINT.md`
  - deployed with Phase E (2026-06-10)

- Slice E2 (Home → stats + workflow shortcuts) implementation status:
  - `V4Home.jsx` rewritten: single `v4API.summary()` call replaces the old `Promise.all([inbox, today, entities.list])`; removed the five duplicate entity-list panels (Review queue, Today, Stuck, Active projects, Inbox flow) and their `HomeSection`/`WorkflowLink`/`EntityList` helpers
  - hero now shows 3 stat cards from `/summary`: in review (`inbox_count`), need attention (`today_count`), day reviewed (`reviewed_today`); below the hero, 3 `ShortcutCard` links (Capture → /inbox, Clear review → /suggestions, Run today → /today)
  - `V4Home.module.css` pruned to hero/shortcut styles only
  - `V4Home.test.jsx` rewritten to mock `v4API.summary` only; 2 tests (hero+shortcuts render from /summary; day-reviewed Yes/No)
  - full UI suite green: 44 passed; build green
  - see `docs/iterations/SLICE_E2_HOME_STATS_SHORTCUTS.md`
  - deployed with Phase E (2026-06-10)

- Slice E3 (Inbox + Review merge) implementation status:
  - removed the "Review" (`/suggestions`) entry from the sidebar `viewItems` and the unused `Sparkles` icon import; `useSidebarCounts` no longer tracks a `suggestions` count
  - `/suggestions` route + `V4Suggestions` view unchanged — stays as a deep-link target from `V4Inbox`'s "Open review queue" links and capture-result suggestion counts
  - `V4Inbox.jsx` already merged capture form + needs-review queue + recent captures — no changes needed there
  - `App.test.jsx` updated: assert "Review" link absent from sidebar
  - full UI suite green: 44 passed; build green
  - see `docs/iterations/SLICE_E3_INBOX_REVIEW_MERGE.md`
  - deployed with Phase E (2026-06-10)

- Slice E4 (Quick capture textarea + sidebar cleanup) implementation status:
  - `QuickActionBar`'s note field is now a plain `<textarea aria-label="Quick note content">` (was `MarkdownEditor`); removed the now-unused `MarkdownEditor` import
  - removed "Agent log" from sidebar `viewItems` and the unused `Activity` icon import; `/agent-activity` route + `V4AgentActivity` view unchanged (deep-link only)
  - `App.test.jsx`: dropped the `MarkdownEditor` mock (real textarea now exercised); asserts "Agent log" link absent from sidebar
  - full UI suite green: 44 passed; build green; full backend suite green: 226 passed (no backend changes)
  - see `docs/iterations/SLICE_E4_QUICK_CAPTURE_SIDEBAR_CLEANUP.md`
  - **Phase E deployed to prod (2026-06-10)**: pre-deploy snapshot taken (`backups/engram_prod_pre_phased_20260610_113920.dump`, no new migration needed), `./scripts/engram-deploy.sh` run, `/api/v4/health` and `/api/v4/summary` smoke-tested OK (`{"inbox_count":1,"last_reviewed_at":null,"reviewed_today":false,"suggestions_count":1,"today_count":39}`)

## Phase F

- Slice F1 (stale projects + suggested archival) implementation status:
  - new `_project_staleness_days(entities, now)` maps active-project id ->
    days since the most recent of `created_at`, latest `activity_update`
    note (`_latest_activity_updates`, reused from D3), or latest
    non-`created` `EntityEvent` (new `_latest_event_at`); `Entity.updated_at`
    can't be used as the trigger `entities_updated_at` forces it to `now()`
    on every UPDATE
  - `GET /api/v4/today` gains `stale_projects` (14-29 days inactive) and
    `suggested_archival` (30+ days inactive), each active project annotated
    via `_entity_with_attention` plus `stale_days`; `GET /api/v4/summary`
    gains `stale_projects_count` (sum of both)
  - Today UI: new collapsible "Stale projects" section (archival items first,
    tagged "consider archiving"); Home hero stats gain a 4th card "stale
    projects" linking to `/today` (`.heroStats` grid now `repeat(4, ...)`,
    `repeat(2, ...)` at the 900px breakpoint)
  - red-first test: 1 new integration test
    (`test_v4_today_surfaces_stale_and_archival_projects`, backdating
    `created_at` for 3 projects); full backend suite green: 227 passed (was
    227, +1 new); UI 44 passed (unchanged count, both edited specs extended);
    build green
  - see `docs/iterations/SLICE_F1_STALE_PROJECTS.md`
  - not deployed — Phase F deploys after F2 (per plan)

- Slice F2 (since-yesterday diff) implementation status:
  - `services/v4_attention.py`: extracted `today_attention_items(...)` (the
    deduped actionable-set list) so both `today_attention_count` and the new
    diff logic share it
  - `_build_today_payload`: computes `since_cutoff` = `now - 24h`, or
    `last_reviewed_at` if more recent; `GET /api/v4/today` and
    `GET /api/v4/summary` gain `new_since_yesterday_count` = entities in
    today's actionable set with `created_at >= since_cutoff`
  - Today UI: summary strip gains a "{n} new since yesterday" pill when > 0
  - red-first test: 1 new integration test
    (`test_v4_today_surfaces_new_since_yesterday_count`, covering the 24h
    window, the post-review reset, and a new item after review); full backend
    suite green: 228 passed (was 228, +1 new); UI 44 passed (unchanged count);
    build green
  - see `docs/iterations/SLICE_F2_SINCE_YESTERDAY_DIFF.md`
  - **Phase F deployed to prod (2026-06-10)**: pre-deploy snapshot taken
    (`backups/engram_prod_pre_phasef_20260610_222745.dump`, no new migration
    needed — additive read-only fields only), `./scripts/engram-deploy.sh`
    run, `/api/v4/health` and `/api/v4/summary` smoke-tested OK
    (`{"inbox_count":0,"last_reviewed_at":null,"new_since_yesterday_count":0,
    "reviewed_today":false,"stale_projects_count":0,"suggestions_count":0,
    "today_count":40}`); `/api/v4/today` confirmed `new_since_yesterday_count`,
    `stale_projects`, `suggested_archival` present
  - **North-star metrics re-run (2026-06-10)**: suggestion accept rate
    15% -> 22.6% (7/31 accepted/dismissed); agent share of state-changes
    ~30% -> 13.8% (25/181, expected per deferred agent-autonomy backlog);
    open tasks invisible to any surface ~60 -> 54. No regressions. See
    `docs/iterations/PHASE_F_NORTH_STAR_METRICS.md`.

- Post-plan follow-up: low-value tentative task suppression
  - extractor prompt now prefers concrete, owner-bearing tasks and avoids
    hedged wording like "maybe", "possibly", and "think about"
  - capture now suppresses obviously tentative low-confidence task candidates
    before they can hit the review queue
  - capture extraction integration suite green: 45 passed
  - full backend suite currently surfaces three unrelated semantic-search
    failures in `tests/integration/test_v4_search.py`; those need follow-up
    before merge

**V4 World Model plan (Phases A-F) complete.** Remaining backlog is all in
"Explicitly deferred" in `docs/V4_WORLD_MODEL_PLAN.md`.

## Post-plan proactive runtime slices

- Runtime coordination/dependency visibility (2026-06-16) implementation status:
  - `GET /api/v4/summary` now returns `coordination_radar`, a runtime-only
    top-of-home artifact derived from existing person/project task state and
    activity-update recency; Home renders a new "Coordination radar" panel
  - `GET /api/v4/entities/<id>/detail` now returns `dependency_watch` for
    both `person` and `project` entities, surfacing blocked work, blockers,
    and tasks blocking downstream work without persisting new inference state
  - `GET /api/v4/today` now returns `dependency_interventions`, giving Today a
    cross-cutting intervention lane for blocker/dependency work; shared
    backend/frontend Today-count logic now includes these intervention
    entities so counts stay aligned with the screen
  - red-first tests added across integration/unit/UI coverage; full backend
    integration suite green: 168 passed; full UI suite green: 59 passed;
    frontend build green
  - no schema changes or migrations required
- Detail page dedupe cleanup (2026-06-16) implementation status:
  - entity detail workspace cards now avoid repeating the same task rows across
    `project` and `person` summary surfaces; relationship segments remain the
    authoritative full/edit lists
  - `project` detail now suppresses "Next step" when that task is already
    surfaced in `Project pulse` or `Dependency watch`
  - `person` detail now dedupes `Meeting prep` and `Current load` against
    `1:1 pulse` and `Dependency watch`, reducing repeated task rows without
    removing the full Assigned Tasks segment
  - repeated AI summary copy was removed from the inspection panel, and
    `Dependency watch` no longer repeats its empty-state message
  - focused backend validation green: 20 passed; full UI suite green: 59
    passed; frontend build green
- Explicit owner identity (2026-06-17) implementation status:
  - `app_settings.owner_person_id` is now the source of truth for "me" when
    configured; old alias matching remains as fallback only when no explicit
    owner person is set
  - new `POST /api/v4/entities/<id>/owner` and `DELETE /api/v4/entities/<id>/owner`
    endpoints allow a `person` entity to be marked/cleared as the owner;
    person detail now returns `entity.is_owner`
  - person detail UI now exposes `Mark as me` / `Clear me` and shows `This is you`
  - coordination and delegation surfaces now honor explicit owner identity:
    `coordination_radar.people` excludes the owner person and
    `delegations_quiet` ignores delegations assigned to the owner person
  - focused backend validation green: 26 passed; full backend integration
    suite green: 171 passed; full UI suite green: 60 passed; frontend build green
- Runtime-only brief + coordination-aware snapshot (2026-06-17) implementation status:
  - `brief` no longer persists to `app_settings.daily_brief`; it now uses a
    small in-process TTL cache only, keeping the artifact runtime-oriented
  - when model generation is unavailable but the workspace has signal,
    `/api/v4/brief` now falls back to a deterministic runtime brief assembled
    from overdue work, dependency interventions, quiet delegations,
    unscheduled attention, stale projects, and coordination radar
  - the model-backed brief snapshot now includes compact `today` and
    `coordination_radar` sections, so newer proactive runtime signals can
    influence the Home brief
  - added red-first integration coverage for the runtime cache path, no-DB
    persistence guarantee, heuristic fallback, and enriched snapshot shape;
    also hardened a flaky UI revert test uncovered in the full-suite rerun
  - focused backend validation green: 5 passed; full backend integration suite
    green: 173 passed; full UI suite green: 60 passed; frontend build green
  - see `docs/iterations/SLICE_POSTPLAN_RUNTIME_BRIEF.md`
- Final validation cleanup (2026-06-17) implementation status:
  - removed the remaining React `act(...)` warnings from `App.test.jsx` by
    waiting for the shell to settle before asserting theme state
  - replaced lingering `Query.get()` test usage with `db.session.get(...)`,
    removing the SQLAlchemy legacy warnings from the touched integration specs
  - hardened `test_capture_auto_created_task_links_to_source_note_projects`
    by mocking reconciliation decisions directly, removing a live-model
    dependency from the integration suite
  - split the frontend build into manual chunks (`vendor-react`,
    `vendor-icons`, `vendor`, plus the app bundle) so the prior Vite
    oversize-chunk warning no longer fires
  - final full validation green: backend `pytest -q` 273 passed; frontend
    `npm test` 60 passed; frontend build passed

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
- 2026-06-26T22:23:27.041618+00:00 untitled-regression-test-react accepted via opencode
- 2026-06-27T16:41:37.222363+00:00 tasks-suggest-only-on-capture accepted via cursor
- 2026-06-27T16:51:22.659853+00:00 last-mile-exact-title-dedup accepted via opencode
- 2026-06-27T18:46:40.276864+00:00 extraction-prompt-sees-active-tasks accepted via cursor
- 2026-06-30T00:30:13.826717+00:00 prd-streaming-capture accepted via cursor
- 2026-07-01T04:29:04.040780+00:00 prd-decisions accepted via opencode
