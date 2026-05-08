# Engram Overnight Execution Tracker

Last updated: 2026-05-07
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
