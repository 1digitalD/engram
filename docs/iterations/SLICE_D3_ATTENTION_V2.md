# Slice D3 — Server-side attention v2 (impact + staleness)

Status: DONE.

## Goal

Per `docs/V4_WORLD_MODEL_PLAN.md` Phase D, Slice D3: attention should account
for impact (this entity blocks other active work) and staleness (no recent
activity), computed via batched relationship context passed through the
existing `context`/kwargs of `attention_for_entity` (the function stays
pure — no DB queries inside it). Undated tasks should be able to rank via
impact + staleness alone, so the large pool of open tasks with no due/follow-
up date can participate in `/today`.

## Changes

### Backend (`services/v4_attention.py`)
- `attention_for_entity` gains two new optional kwargs:
  - `staleness_days` — days since the entity's last activity. Weighted via a
    tiered table (`STALENESS_THRESHOLDS`): `>=21d -> 25`, `>=14d -> 18`,
    `>=7d -> 10`, `>=3d -> 4`, else 0. Adds a `staleness` reason
    (`"no update in N days"`) when non-zero.
  - `blocks_count` — how many other active, non-done entities this entity
    blocks. Weighted `min(24, blocks_count * 12)` (`IMPACT_WEIGHT_PER_BLOCK`
    / `IMPACT_WEIGHT_CAP`). Adds an `impact:blocks` reason
    (`"blocks N other item(s)"`) when non-zero.
- Both inputs are computed by the caller via batched queries; the function
  remains pure.

### Backend (`api/v4_entities.py`)
- New `PRIORITY`-adjacent batched helpers:
  - `_staleness_days_for(entities, now)` — maps `entity_id -> days since last
    activity`, using the existing `_latest_activity_updates` for the most
    recent activity-update note, falling back to `entity.created_at` (one
    batched query, plus the existing activity-update query).
  - `_blocking_impact_counts(entities)` — one grouped query mapping
    `entity_id -> count` of active, non-done entities it blocks via a
    `blocks` `EntityLink`.
- `_entity_with_attention` threads `staleness_days` and `blocks_count`
  through to `attention_for_entity`.
- `GET /api/v4/today`:
  - New query for unscheduled open tasks (`type=task`, active, status in
    `OPEN_TASK_STATUSES`, `due_at IS NULL AND follow_up_at IS NULL`),
    capped at 100.
  - Staleness and impact are computed once (batched) across all task
    buckets including the new unscheduled set, and threaded through the
    existing `with_priority` closure.
  - The unscheduled set is scored, sorted by attention score descending,
    filtered to `score > 0`, and capped at 20 — returned as a new
    `unscheduled_attention_tasks` bucket.

### Frontend
- `ui/src/views/V4Today.jsx`: new "Needs attention (no date set)" section
  rendering `unscheduled_attention_tasks` (no special `reason` pill beyond
  the standard attention pill).
- `ui/src/utils/today.js`: new `getTodayUnscheduledAttentionEntities`;
  `getTodayAttentionCount` includes these items in the daily total.
  `getTodayFocusItems` deliberately does NOT include this bucket — mixing
  high-staleness-score undated tasks into "Focus now" displaced existing
  high-signal captured-note items in testing, which felt like the wrong
  trade-off for this slice. The new section is visible on its own.

## Tests (TDD, red → green)

- `tests/unit/test_v4_attention.py`:
  - `test_attention_staleness_weight_table` — pins the staleness weight
    table across all threshold boundaries (0, 2, 3, 6, 7, 13, 14, 20, 21,
    40 days).
  - `test_attention_impact_weight_table` — pins the impact weight table
    (0, 1, 2, 3 blocked items → 0, 12, 24, 24).
  - `test_attention_undated_high_priority_stale_task_outranks_dated_low_priority_task`
    — per the D3 acceptance criterion: an undated `priority: high` task
    stale for 14 days (score 43) outscores a dated `priority: low` task due
    today (score 37).
- `tests/integration/test_v4_today.py::test_v4_today_surfaces_unscheduled_tasks_by_impact_and_staleness`
  — a stale (21 days, via backdated `created_at`) high-priority undated task
  and a task that `blocks` another active task both appear in
  `unscheduled_attention_tasks` with the expected `staleness` /
  `impact:blocks` reasons; a quiet undated task with no signal does not
  appear.
- `ui/src/views/V4Today.test.jsx` — extended with an
  `unscheduled_attention_tasks` fixture item; asserts the new section
  renders and the daily attention count increments accordingly (8 → 9).

Full backend suite green: 221 passed (was 217; +4 new). Frontend: 43 passed,
build green. Live-checked against prod `/today` on a scratch port (5099,
job worker process killed immediately after): 20 unscheduled tasks surfaced
with correct `staleness`/`impact` reasons; no writes performed.

## Acceptance criteria

- [x] Unit tests pin the staleness and impact scoring tables.
- [x] An undated high-priority stale task outranks a dated low-priority task
      (unit-tested directly per spec).
- [x] `/today` surfaces previously-invisible undated open tasks via a new
      `unscheduled_attention_tasks` bucket, computed with batched queries
      (no N+1).
- [x] Suite + UI green.

Not yet deployed.
