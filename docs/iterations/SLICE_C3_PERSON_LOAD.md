# Slice C3 — Person workspace: load + last-heard

Status: DONE.

## Goal

Per `docs/V4_WORLD_MODEL_PLAN.md` Phase C, Slice C3: a person's detail page
should show their full current load (open assigned tasks) with last-heard
context, not just a single "primary task" pointer.

## Changes

### Backend (`api/v4_entities.py`)
- `GET /api/v4/entities/<id>/detail` now includes a `current_load` field for
  `person` entities: a list of that person's open tasks (status in
  `OPEN_TASK_STATUSES`), ordered by `follow_up_at` (soonest first, nulls
  last) then `updated_at` desc, capped at 50.
- Each item is `{ task: <entity-with-attention>, last_heard_at, last_heard_preview }`,
  where `last_heard_at`/`last_heard_preview` come from the most recent
  `activity_update` note linked to that task (or `null`/`null` if none).
- New `_person_current_load(person)` helper.
- Refactored `_latest_activity_updates(entity_ids)` out of Slice C2's
  `_delegations_quiet` so both features share the same batched
  (no N+1) lookup of each entity's latest activity-update note.

### Frontend (`ui/src/views/V4EntityDetail.jsx`)
- `PersonWorkspacePanel`'s "Current load" card now lists every item in
  `detail.current_load` (previously showed at most one "primary task").
  Each row shows the task title, status, priority (if set), and either
  "Last heard {date} — {preview}" or "No activity update yet".

## Tests (TDD, red → green)

- `tests/integration/test_v4_today.py::test_v4_person_detail_includes_current_load_with_last_heard`
  — a person with one open task (with an activity update) and one done task;
  asserts `current_load` includes the open task with a non-null
  `last_heard_at`/`last_heard_preview`, and excludes the done task.
- `ui/src/views/V4EntityScreens.test.jsx` — extended the existing person
  workspace test with a `current_load` of two tasks (one with a last-heard
  preview, one without) and asserted both render correctly.

Full backend suite green: 207 passed (was 206; +1 new). Frontend: 43 passed,
build green.

## Acceptance criteria

- [x] A person's page lists their open tasks with last-heard timestamps.
- [x] Suite + UI green.

Not yet deployed — per the plan, Phase C deploys once after Slice C4.
