# Slice C2 — "Gone quiet" surfacing in /today

Status: DONE.

## Goal

Per `docs/V4_WORLD_MODEL_PLAN.md` Phase C, Slice C2: surface delegations whose
`follow_up_at` (set by Slice C1's cadence logic) has passed with no activity
update since, so the owner sees who needs a nudge.

## Changes

### Backend (`api/v4_entities.py`)
- `GET /api/v4/today` gains `delegations_quiet`: a list of tasks where
  - assigned (via `assigned_to` link) to a `person` who is not an owner alias
    (per `_owner_aliases()`),
  - `follow_up_at` is set and in the past,
  - not in a done/cancelled status,
  - and no `activity_update` note linked to the task was created on/after
    `follow_up_at`.
  Each item is the usual entity-with-attention payload plus `days_silent`
  (days since the last activity update, or since `follow_up_at` if there has
  never been one) and `last_update` (a 160-char preview of the latest
  activity-update note's content, or `null`).
- New `_delegations_quiet(now)` helper: two batched queries (delegated tasks
  via an `aliased` person join, then one query for the latest activity-update
  note per task id) — no N+1.

### Frontend (`ui/src/views/V4Today.jsx`)
- New "Delegations needing a nudge" section (hidden when empty), rendered
  after "Recent notes". Each row shows the task title, an excerpt of its last
  activity update (if any), and a `"<N> days silent"` pill, or "no activity
  update yet" when there has never been one.

## Tests (TDD, red → green)

Added to `tests/integration/test_v4_today.py`:
- `test_v4_today_surfaces_quiet_delegations` — a task delegated to "Akash"
  with `follow_up_at` 10 days ago and no activity update appears with
  `days_silent >= 9` and `last_update: null`; a task with a fresh activity
  update (which also re-triggers C1's cadence refresh) does not appear; a task
  whose `follow_up_at` is still in the future does not appear.
- `test_v4_today_does_not_surface_delegations_to_owner` — a task delegated to
  "Dan" (the owner) never appears in `delegations_quiet`.

Added to `ui/src/views/V4Today.test.jsx`: asserts the new section renders with
the delegated task title and "10 days silent".

Full backend suite green: 206 passed (was 204; +2 new). Frontend: 43 passed,
build green. Live QA against prod `/today` confirms the section renders
without errors and is correctly hidden (no quiet delegations exist yet in
prod data).

## Acceptance criteria

- [x] A delegation with no update past cadence appears with correct
      `days_silent`.
- [x] A delegation with a fresh update does not appear.
- [x] Suite + UI green.

Not yet deployed — per the plan, Phase C deploys once after Slice C4.
