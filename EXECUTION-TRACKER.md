# Engram Overnight Execution Tracker

Last updated: 2026-05-07
Worktree: `/Volumes/lex1t/dev/shared/repos/engram/.claude/worktrees/reverent-knuth-45dc53`
Branch: `claude/reverent-knuth-45dc53`

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
- [ ] Batch 2 committed
- [ ] Batch 3 started
- [ ] Batch 3 committed

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
- Next step: commit Batch 2 store/palette changes now that validation is green, then decide whether a bounded Batch 3 UI slice is worth the risk tonight.

## Recovery notes
If the session resets or the gateway restarts:
- Re-open this file first
- Check `git status` and latest commits in this worktree
- Resume the first unchecked item in `Status`
- Re-run the last incomplete validation command before continuing
