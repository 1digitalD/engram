# Slice D1 — Project priority, inherited by tasks

Status: DONE.

## Goal

Per `docs/V4_WORLD_MODEL_PLAN.md` Phase D, Slice D1: priority already lives in
`properties.priority`. Formalize it: tasks with no priority of their own
should rank using their parent project's priority, and there should be a way
for Dan to quickly review/set initial project priorities.

## Changes

### Backend (`services/v4_attention.py`)
- `attention_for_entity` gains an optional `inherited_priority` kwarg. The
  effective priority is `own_priority or inherited_priority`. When the
  effective priority comes from `inherited_priority` (the entity has no own
  `properties.priority`), the `priority:<level>` reason's label gets a
  `" (from project)"` suffix so the source is visible in attention reasons.
  The function remains pure — no DB queries.

### Backend (`api/v4_entities.py`)
- New `_inherited_task_priorities(tasks)`: one batched query mapping
  `task_id -> parent project's properties.priority`, for tasks (in the given
  list) that have no `properties.priority` of their own and a `parent` link
  to a project with a priority set.
- `_entity_with_attention` gains an `inherited_priority` kwarg, passed through
  to `attention_for_entity`; when used, the entity dict also gets
  `inherited_priority: "<level>"` (omitted when the entity has its own
  priority).
- `GET /api/v4/today`: computes `_inherited_task_priorities` once across all
  task buckets (`overdue`, `due_today`, `overdue_follow_ups`, `follow_ups`,
  `upcoming_follow_ups`, `blocked_tasks`, `waiting_tasks`) and threads the
  result through `_entity_with_attention` for each item via a small
  `with_priority` closure.

### Frontend (`ui/src/views/V4Today.jsx`)
- `EntityRow` now shows a `~<priority>` pill (titled "Inherited from project")
  when an item has `inherited_priority` and no `properties.priority` of its
  own, alongside the existing `!<priority>` pill for own priority.

### One-time assist (`scripts/list_project_priorities.py`, new)
- Read-only script listing all active projects with their current
  `properties.priority` (or `(none)`), so Dan can see at a glance which
  projects still need a priority set and bulk-edit them via the Projects list
  UI (priority is already editable per-entity through the existing generic
  priority control).

## Tests (TDD, red → green)

- `tests/unit/test_v4_attention.py`:
  - `test_attention_uses_inherited_priority_when_own_is_unset` — a task with
    no `properties.priority` and `inherited_priority="high"` gets a
    `priority:high` reason (weight 25) labeled `"high priority (from
    project)"`.
  - `test_attention_prefers_own_priority_over_inherited` — a task with its own
    `priority: "low"` and `inherited_priority="urgent"` keeps `priority:low`,
    with no "(from project)" suffix.
- `tests/integration/test_v4_today.py::test_v4_today_task_inherits_project_priority`
  — a project with `properties.priority="urgent"`, two overdue tasks
  parent-linked to it (one with no own priority, one with `priority: "low"`);
  asserts the first gets `inherited_priority: "urgent"` and an attention
  reason labeled with "(from project)", and the second has neither.
- `ui/src/views/V4Today.test.jsx` — extended with an overdue item carrying
  `inherited_priority: "urgent"` and asserts the `~urgent` pill renders.

Full backend suite green: 213 passed (was 210; +3 new). Frontend: 43 passed,
build green. Live QA against prod `/today` confirms no regressions (no prod
project currently has a priority set, so no `~<priority>` pill renders yet —
expected).

## Acceptance criteria

- [x] A task with no own priority ranks (via attention reasons/score) using
      its project's priority.
- [x] Suite + UI green.

Not yet deployed.
