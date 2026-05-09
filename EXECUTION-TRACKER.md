# Engram Overnight Execution Tracker

Last updated: 2026-05-09
Worktree: `/Volumes/lex1t/dev/shared/repos/engram/.claude/worktrees/reverent-knuth-45dc53`
Branch: `overhaul/full-implementation-loop`

## Operating principles
- No corner-cutting
- TDD or test-first where practical
- Validate at each step before moving on
- Commit in logical, reviewable units
- Keep durable notes in this file so work survives session resets/restarts
- Prefer reconciling the plan to the actual repo over blindly following stale file references

## Repo reality check
The current `PLAN.md` is directionally strong but not fully aligned to the present worktree.
Notable mismatches already verified:
- `migrations/` directory does not exist yet
- Several planned UI component paths do not exist in this tree
- The plan should be executed as a reconciled sequence, not a single blind agent run

## Tonight scope
Primary objective: execute the highest-value Phase 1 work that fits the current codebase cleanly.

### Batch 1: Backend foundation
- Reconcile schema/API changes from P1-WS1 to actual models/routes
- Add missing `area_id` on `Project`
- Add missing `area_id` and `note_id` on `Task`
- Add reverse relationships and serialization updates
- Add/adjust migration strategy appropriate to this repo
- Add or extend backend tests first
- Validate with targeted pytest
- Commit

### Batch 2: Store completeness
- Reconcile P1-WS3 with actual Zustand store shape
- Add missing area/person update/delete flows
- Add `captureOpen`, `openCapture`, `closeCapture`
- Pass through `due_date`, `area_id`, `note_id` for task create/update
- Add tests if present/feasible, otherwise validate through targeted inspection and app build
- Commit

### Batch 3: UI slice only if Batch 1-2 are green and time allows
- Choose one bounded UI flow that matches current file layout
- Prefer lowest-risk/highest-value work from plan
- Validate with frontend build and targeted checks
- Commit

## Execution protocol
For each batch:
1. Inspect current code and adapt plan to reality
2. Write failing or gap-exposing tests first when practical
3. Implement minimum clean change
4. Run targeted validation
5. If green, commit with a focused message
6. Update this tracker with status, evidence, and next step

## Status
- [x] Batch 1 started
- [x] Batch 1 committed
- [x] Batch 2 started
- [x] Batch 2 committed
- [x] Batch 3 started
- [x] Batch 3 committed

## Progress log
### 2026-05-07
- Created overnight tracker and narrowed scope to executable batches aligned with actual repo state.
- Inspected backend models/routes/tests. Confirmed repo uses `db.create_all()` plus one-off migration scripts, not Alembic/migrations.
- Added red coverage in `tests/test_phase1_backend_foundation.py` for `Project.area_id`, `Task.area_id`/`note_id`, serialization, and API filtering/update flows.
- Bootstrapped a local `.venv` for validation because this worktree did not have pytest available. Full `requirements.txt` install failed on unavailable `fastmcp`, so I installed the runtime/test subset needed for backend validation instead.
- Implemented Batch 1 schema/API changes in `models.py`, `api/projects.py`, `api/tasks.py`, and added idempotent migration script `migrate_area_task_project_fields.py` aligned with this repo's current migration style.
- Fixed an unrelated pre-existing test bug in `tests/test_models.py`: `Person` does not accept `discord_id`; current schema uses `external_ids`.
- Targeted backend validation passed: `source .venv/bin/activate && PYTHONPATH=. pytest -q tests/test_phase1_backend_foundation.py tests/test_models.py tests/test_api.py` → `24 passed in 0.33s`.
- Started Batch 2 in the actual Zustand store and command palette files that exist in this tree.
- Added `captureOpen`, `openCapture`, `closeCapture`, plus `updateArea`/`deleteArea` and `updatePerson`/`deletePerson` store actions.
- Normalized `createTask`/`updateTask` payloads so `due_date`, `area_id`, and `note_id` pass through explicitly, including null clears.
- Fixed command palette routing for area hits and wired “Capture note” to open the capture overlay state instead of navigating.
- Re-validated Batch 1 before commit: backend pytest stayed green.
- Committed Batch 1 as `db9c961` (`Add area and note relationships for projects and tasks`).
- Frontend validation is possible, but this worktree does not track `ui/node_modules`, so `npm install && npm run build` is required each time; current build is green after install.
- Committed Batch 2 as `ba3e46e` (`Complete missing store actions and capture state`).
- Batch 3 completed: three bounded UI slices from Phase 1 are implemented, validated, and committed.
- Remaining PLAN.md work should be converted into small prd.json tasks before execution; do not hand the whole plan to a coding agent as one task.


### 2026-05-08
- Started Batch 3 using the self-improving coding loop contract (`AGENTS.md` + `prd.json`) in this worktree.
- Task `p1-ws2-note-cards-markdown-display` implemented via isolated OpenClaw code-agent session `xDGi9yf8`; plugin merge targeted `main` for this nested tracker worktree, so the validated source-only patch was applied manually onto `claude/reverent-knuth-45dc53`.
- Implemented markdown note-card previews, expand/collapse, tag URL filtering, demoted AI badge styling, Notion import metadata placeholder, and missing `.spin` CSS.
- Validation passed: `cd ui && npm install && npm run build` (Vite chunk-size warning only). Generated static assets were reverted to keep the commit source-only.
- Committed as `2200044` (`Improve note card markdown display`).
- Next loop task from `prd.json`: `p1-ws3-area-person-task-ui`.
- Task `p1-ws4-note-detail-inline-editing` implemented via isolated OpenClaw code-agent session `yKfVif2V`; validated source-only patch applied onto tracker branch.
- Implemented inline note-detail editing with Save/Cancel, Esc cancel, Cmd/Ctrl+Enter save, plus Write/Preview tabs in `NoteEditor`.
- Validation passed: `cd ui && npm install && npm run build` (Vite chunk-size warning only). Generated static assets were reverted.
- All tasks in `prd.json` are now passing.

- Task `p1-ws3-area-person-task-ui` implemented via isolated OpenClaw code-agent session `-A-zIJf7`; plugin placed the validated changes in the base tracker worktree while awaiting worktree decision.
- Implemented area edit/delete controls, area detail edit/delete, person edit/delete controls, inline task title editing, task creation due date support, and scoped CSS support.
- Validation passed: `cd ui && npm install && npm run build` (Vite chunk-size warning only). Generated static assets were reverted.



### 2026-05-08 branch policy update
- Created integration branch `overhaul/full-implementation-loop` at validated HEAD `6744563`.
- Policy: continue all remaining overhaul phases by merging validated task work into `overhaul/full-implementation-loop`. Do not merge to `main` until all phases are complete and end-to-end validation passes.

- Task `p1-ws1-daily-notes-api` implemented via isolated OpenClaw code-agent session `nKddrk5d`; validated patch was manually applied to `overhaul/full-implementation-loop` to avoid merging the nested agent branch onto `main`.
- Added `api/daily.py`, registered daily routes in `api/__init__.py`, and extended `tests/test_api.py` for daily create, fetch existing INBOX daily note, and append behavior.
- Validation passed after applying the patch: `source .venv/bin/activate && PYTHONPATH=. pytest -q tests/test_phase1_backend_foundation.py tests/test_models.py tests/test_api.py` → `27 passed in 0.37s`.
- The previous tracker branch `claude/reverent-knuth-45dc53` remains historical context; this branch is the new source of truth for overhaul integration.


### 2026-05-08 PLAN.md execution policy
- `PLAN.md` is the canonical long-form backlog for the overhaul.
- `prd.json` is the executable queue. The coding loop must not free-form execute the full plan directly.
- When `prd.json` has no pending tasks, reconcile `PLAN.md` against current repo state and append the next small dependency-ordered tasks with concrete acceptance criteria.
- Execute one `prd.json` task per isolated agent session, validate, commit to `overhaul/full-implementation-loop`, update task status, then continue.

## Recovery notes
If the session resets or the gateway restarts:
- Re-open this file first
- Check `git status` and latest commits in this worktree
- Resume the first unchecked item in `Status`
- Re-run the last incomplete validation command before continuing


- Task `p1-ws1-inline-task-extraction` implemented via Cursor executor worktree and applied to `overhaul/full-implementation-loop`.
- Files changed: api/batch.py, api/daily.py, api/notes.py, migrate_task_inline_title_hash.py, models.py, services/extractor.py, services/ingestion.py, tests/test_api.py.
- Validation passed: 31 passed in 0.46s.


- Task `p1-ws4-note-detail-panels-and-today` implemented via Cursor executor worktree and applied to `overhaul/full-implementation-loop`.
- Files changed: ui/src/App.jsx, ui/src/api/engram.js, ui/src/components/layout/AppShell.jsx, ui/src/stores/useStore.js, ui/src/views/Inbox.jsx, ui/src/views/Inbox.module.css, ui/src/views/NoteDetailView.jsx, ui/src/views/NoteDetailView.module.css, ui/src/views/Today.jsx, ui/src/views/Today.module.css.
- Validation passed: - Adjust chunk size limit for this warning via build.chunkSizeWarningLimit..

- Task `p1-ws5-navigation-layout-polish` completed in worktree `engram-p1-ws5-navigation-layout-polish`.
- Scope: top bar with Sun→Today, app shell body with sidebar+main, mobile drawer+bottom nav, AreaFocus projects/tasks tabs, ProjectFocus area breadcrumb, graph Open action, command palette categories and keyboard hints, note detail breadcrumb, captureOpen→NoteEditor wiring.
- Validation: `cd ui && npm install && npm run build` passed (chunk size warning only); `static/` reverted to source-only (no generated assets in commit).

- Task `p1-ws6-power-features` completed in worktree `engram-p1-ws6-power-features`. QuickCapture overlay tied to `captureOpen`/`openCapture`/`closeCapture`; `⌘N`/`Ctrl+N` quick capture, `⌘⇧N` full NoteEditor; shortcuts help modal (`⌘/`/`Ctrl+/` + header button); interactive task toggles on Dashboard, Today, Tasks board, Project/Area focus tabs; fixed AreaFocus tabs array (removed stray icon identifiers). Validation: `cd ui && npm install && npm run build` green; static build output reverted before commit.

- Task `p2-ws2-typed-resources-schema-api`: `Resource` model + `ResourceType` enum, `resource_tags` M2M, `Area.resources` + `Area.resource_count` in serialization, CRUD `/api/v1/resources` with `GET ?type=` filter, migration `006_resource_model.py`; `prd.json` task marked passes. Validation: `PYTHONPATH=. pytest -q tests/test_api.py` → 25 passed.

- Task `p2-ws2-ui-resources-list-detail`: Resources list (`Resources.jsx`) with type chips, title search, cards (type icon, author, stars, read badge); detail (`ResourceDetail.jsx`) with full inline edit form and area link; `AppShell` Library nav item; routes in `App.jsx`; `resourcesAPI` + store `resources` in `loadAll`, `updateResource`, `deleteResource`, `upsertResource`. Validation: `cd ui && npm install && npm run build` green; `static/` left source-only (build artifacts removed).

- Task `p3-ws1-iter-b-summarization-service`: `services/summarizer.py` (`Summarizer.summarize_notes`, Claude Sonnet via Anthropic, ~1500 est. token note chunks by date newest-first, hierarchical merge of partial JSON); `api/summarize.py` `POST /api/v1/summarize`; `anthropic` in `requirements.txt`; `GET/DELETE` summaries unchanged on `api/summaries.py`. Validation: `PYTHONPATH=. pytest -q tests/test_api.py` → 29 passed.

- Task `p3-ws1-iter-c-scheduled-background-jobs`: `api/jobs.py` (`POST /api/v1/jobs/summarize`, `GET /api/v1/jobs/status`); `Summarizer.execute_scheduled_summarization` + `run_async` for last-7-days area rollups; optional `Summary.area_id` + migration `008_summary_area_id.py` and `007` DDL/backfill; `TestingConfig.JOBS_SYNC` for deterministic tests; OpenClaw doc `openclaw/weekly-summarization-cron.md` (Sunday 09:00 America/Los_Angeles). Validation: `OPENAI_API_KEY=dummy PYTHONPATH=. pytest -q tests/test_api.py` → 32 passed (dummy key avoids async embed sqlite-vec flake with real credentials).

- Task `p3-ws1-iter-d-review-view-overhaul`: `Review.jsx` + `Review.module.css` (summaries via `summariesAPI` in `engram.js`) — dynamic Review header for selected granularity/period; date picker with prev/next period; Day/Week/Month control; progressive disclosure (collapsible themes + narrative; narrative defaults closed when themes exist); expandable long narrative; action items list. Quadrants unchanged. Validation: `cd ui && npm install && npm run build` green (chunk warning only); `static/` source-only.

- Task `p3-ws2-iter-a-proposal-generation`: `services/link_proposer.py` with `propose_links()` (semantic via sqlite-vec when not in TESTING, lexical Jaccard fallback, shared entities: area/tags/projects/person, temporal boost; skips existing `Link` rows; canonical from/to by created_at). Tests: `tests/test_link_proposer.py`. `services/embeddings.py`: `from __future__ import annotations` for Python 3.9, skip `embed_note` under `TESTING` (stabilizes pytest with background threads). Validation: `OPENAI_API_KEY=dummy PYTHONPATH=. pytest -q tests/test_phase1_backend_foundation.py tests/test_models.py tests/test_api.py tests/test_link_proposer.py` → 51 passed.

- Task `p3-ws2-iter-b-proposals-api`: `api/proposals.py` registered from `api/__init__.py` — `GET /api/v1/proposals` (pending by default, `?status=` / `?limit=`); `POST /api/v1/proposals/generate` (runs `propose_links`, persists `LinkProposal` rows); `POST /api/v1/proposals/<id>/accept` (creates `related` `Link`, marks accepted); `POST /api/v1/proposals/<id>/dismiss`. Renamed `link_proposer` TypedDict to `ProposedLink` to avoid clashing with `models.LinkProposal`. Tests in `tests/test_api.py`. Validation: `OPENAI_API_KEY=dummy PYTHONPATH=. pytest -q tests/test_phase1_backend_foundation.py tests/test_models.py tests/test_api.py tests/test_link_proposer.py` → 55 passed.

- Task `p3-ws2-iter-c-ui-proposals-notedetail`: Note detail “Suggested links” panel (`GET /api/v1/proposals?status=pending&note_id=…`) with Accept / Dismiss; `proposalsAPI` in `engram.js`; `note_id` filter on proposals list + test `test_link_proposals_list_filter_by_note_id`. Confirmed outgoing links + backlinks unchanged in same panel. Committed `0723efe` (`p3-ws2-iter-c-ui-proposals-notedetail: note detail proposals panel and note_id filter`). Validation: `cd ui && npm install && npm run build` green; targeted pytest with venv + `OPENAI_API_KEY=dummy` → 56 passed.

- Task `p3-ws2-iter-d-ui-proposals-review`: `Review.jsx` + `Review.module.css` — “Pending link proposals” queue (`GET /api/v1/proposals`, pending, limit 500): paired note titles/context via store notes + cached miss hints, confidence/date/reason, row Accept/Dismiss, checkboxes with Select all / Clear selection, bulk Accept selected / Dismiss selected, Accept all (sequential API calls + reload). Committed `84f0a2b` (`p3-ws2-iter-d-ui-proposals-review: pending proposals queue on Review with bulk actions`). Validation: `cd ui && npm install && npm run build` green (chunk warning only); `static/` left unchanged / source-only.

- Task `p4-ws1-iter-a-review-workflow`: seven-step guided Weekly Review (`reviewWorkflowState.js`, `usePersistedReviewWorkflow`), progress rail with prev/next/focus, collapsible panels + “Reviewed” checkboxes persisted under `engram.reviewWorkflow.v1`, reset workflow. `Review.test.jsx` + `reviewWorkflowState.test.js`; `setupTests.js` Map-backed `localStorage` for Vitest reliability. Committed `d3583a2`. Validation: `cd ui && npm install && npm test -- --testPathPattern=Review` (3 passed); `npm run build` green (chunk warning only). `static/` not committed.

- Task `p4-ws1-iter-b-orphan-note-review`: `Review.jsx` + `Review.module.css` — orphan list uses `link_count === 0`, no project/area, excludes INBOX; per-note project/area `<select>` (calls `updateNote`), Quick link (`navigate` to note detail), Archive row; bulk Archive all orphans + `window.confirm`; `useStore.updateNote(id, data, { silent })` for bulk without toast spam. Tests: orphan filter + bulk archive. Committed `5962bd4`. Validation: `cd ui && npm test -- --testPathPattern=Review` → 5 passed.

- Task `p4-ws1-iter-c-weekly-digest-card`: `GET /api/v1/review/weekly-digest` (`api/review.py`) — rolling UTC counts for notes created, tasks created, archived projects by `modified_at`, links created; `reviewAPI` + digest card at top of `Review.jsx` (above workflow rail); CSS `digestCard`; tests in `tests/test_api.py` + `Review.test.jsx`. Committed `5c0b1cb`. Validation: `pytest tests/test_phase1_backend_foundation.py tests/test_models.py tests/test_api.py` → 54 passed; `cd ui && npm test -- --testPathPattern=Review` → 6 passed.

- Task `p4-ws2-iter-a-health-metrics-api`: `GET /api/v1/metrics/health` (`api/metrics.py`) — DB-backed `total_notes`, `orphan_rate`, `avg_links_per_note`, `inbox_count`, `archive_ratio`, `tag_coverage`, `active_projects`, `stale_projects` (active projects with `modified_at` older than 30 days), `weekly_capture_rate` (notes created in the last 7 days), `link_proposals_pending`. Registered in `api/__init__.py`. Tests: `test_api_v1_metrics_health_empty`, `test_api_v1_metrics_health_from_db` in `tests/test_api.py`. Validation: `python3 -m pytest tests/test_api.py -k health` → 3 passed; full backend slice → 56 passed.

- Task `p4-ws2-iter-b-dashboard-health-card` (commit `deb9793`): Dashboard "Knowledge Health" card — `metricsAPI.health` + `weekly_capture_counts` (4 rolling weeks) on `GET /api/v1/metrics/health`; `Dashboard.jsx` / `Dashboard.module.css` — orphan rate tier colors, avg links, 7d capture count, inbox urgency (warn if count greater than 20, bad if greater than 50), mini bar chart; `Dashboard.test.jsx`. Validation: `pytest tests/test_api.py -k health` → 3 passed; `cd ui && npm test -- --testPathPattern=Dashboard` → 4 passed; `npm run build` green (static artifacts reverted before commit).

- Task `p4-ws2-iter-c-health-history`: Weekly health snapshots as `Summary` rows (`entity_type=system`, `granularity=WEEKLY`, metrics in `key_themes`), upsert on `GET /api/v1/metrics/health`; stable ARCHIVES anchor note excluded from health aggregates; `GET /api/v1/metrics/health/history?weeks=12`; summaries list hides system rows unless `?entity_type=system`; Review Insights tabs with **System Health** twelve-week SVG trend (`orphan_rate`, `capture_rate`). Migration `migrations/009_summary_entity_type.py`. Validation: `pytest tests/test_phase1_backend_foundation.py tests/test_models.py tests/test_api.py` → 60 passed; `cd ui && npm test -- --testPathPattern=Review` → 7 passed; `npm run build` green (chunk warning only); static build artifacts not committed.
