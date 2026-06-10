# Slice C1 — Delegation detection + cadence

Status: DONE.

## Goal

Per `docs/V4_WORLD_MODEL_PLAN.md` Phase C, Slice C1: tasks assigned to someone
other than the owner ("Dan") are delegations. On creation/assignment, set
`follow_up_at` to now + cadence (default 3 working days) unless already dated.
An activity update on a delegated task refreshes (pushes forward) that
`follow_up_at` by the cadence again.

## Changes

### Schema (additive)
- New `app_settings` key/value table (`key TEXT PRIMARY KEY`, `value JSONB`,
  `updated_at`). Holds owner identity aliases and per-person cadence overrides.
  No rows are required — code falls back to defaults (`owner_aliases: ["dan"]`,
  `default_cadence_days: 3`) when settings are absent.
- `docs/SCHEMA.sql` updated; `scripts/migrations/002_add_app_settings.sql` added
  for prod (idempotent `CREATE TABLE IF NOT EXISTS`).

### Backend (`api/v4_entities.py`, `models.py`)
- New `AppSetting` model (`app_settings` table).
- New helpers:
  - `_get_app_setting(key, default)` / `_owner_aliases()` / `_is_owner(name)`
  - `_delegation_cadence_days(person_id=None)` — checks `cadence_overrides` by
    person id, else `default_cadence_days`, else `DEFAULT_DELEGATION_CADENCE_DAYS`
    (3).
  - `_add_working_days(start, days)` — adds N weekday days, skipping Sat/Sun.
- `_apply_assignee`: when a `task` is linked `assigned_to` a person who is not
  the owner, and the task has no `follow_up_at` yet, sets
  `follow_up_at = now + cadence working days` and records an `ai_updated`
  `EntityEvent` (`old_value: {follow_up_at: null}` → `new_value: {follow_up_at:
  ...}`, `reason: "delegation cadence"`, `source_note_id` when capture-driven).
  This covers both the capture pipeline and suggestion-accept paths, since both
  funnel through `_apply_assignee`.
- `_create_activity_update_note`: after recording `activity_update_added`, calls
  new `_refresh_delegation_cadence(target, source_note_id, actor)`. If `target`
  is a `task` assigned to a non-owner person, pushes `follow_up_at` forward to
  `now + cadence working days` and records another `ai_updated` `EntityEvent`
  (`reason: "delegation cadence refresh"`).

## Tests (TDD, red → green)

Added to `tests/integration/test_v4_capture_extraction.py`:
- `test_capture_assigns_delegation_sets_follow_up_at_cadence` — capturing
  "Akash: design GTM trigger doc" creates a task assigned to Akash with
  `follow_up_at ≈ now + 3 working days` and an `ai_updated` event.
- `test_capture_does_not_set_cadence_for_owner_assignee` — assigning to "Dan"
  (the owner) leaves `follow_up_at` unset.
- `test_activity_update_refreshes_delegation_follow_up_at` — posting an
  activity update to a task already assigned to a non-owner person with a
  stale `follow_up_at` pushes it forward to `now + cadence`.

`tests/unit/test_models.py`: `V4_TABLES` updated to include `app_settings`.

Full suite green: 204 passed (was 201; +3 new).

## Acceptance criteria

- [x] Capturing "Akash: design GTM trigger doc" yields a task assigned to Akash
      with `follow_up_at ≈ +3 working days`.
- [x] An activity update on that task refreshes `follow_up_at`.
- [x] Suite green.

Not yet deployed — per the plan, Phase C deploys once after Slice C4.
