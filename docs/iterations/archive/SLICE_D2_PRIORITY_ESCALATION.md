# Slice D2 — Priority escalation from capture

Status: DONE.

## Goal

Per `docs/V4_WORLD_MODEL_PLAN.md` Phase D, Slice D2: when a captured note
expresses urgency escalation about an existing entity (e.g. "this is now
urgent", "escalating this"), the system should be able to suggest raising
that entity's `properties.priority` — never auto-applied, always reviewed.
Also formalize `priority` as an acceptable field on the existing
`update_entity` suggestion accept path.

## Changes

### Backend (`api/v4_entities.py`)
- New `PRIORITY_LEVELS = {"low", "medium", "high", "urgent"}` and
  `PRIORITY_ORDER = {"low": 1, "medium": 2, "high": 3, "urgent": 4}`.
- `_accept_update_entity_suggestion`: `fields` now also accepts `"priority"`.
  When present, validates against `PRIORITY_LEVELS` (400 on invalid value)
  and, if different from the current value, writes
  `target_entity.properties["priority"]`. The change is captured by the
  existing `updated` event (old/new snapshot diff) — no new event type.
- `_apply_reconciliation_decision`'s `progress_update` branch: after the
  existing status handling, if the decision's `fields.priority` is a valid
  level strictly higher (per `PRIORITY_ORDER`) than the target's current
  `properties.priority` (or the target has none), a suggestion is created via
  `_append_capture_suggestion` with `operation_type="update_entity"` and
  `payload.fields={"priority": "<level>"}`. This happens regardless of
  confidence — priority escalation is never auto-applied.

### Backend (`services/v4_reconciliation.py`)
- `SYSTEM_PROMPT`'s `progress_update` section: `fields` now documents both
  `status` (unchanged) and `priority`. `priority` should only be populated
  when the update text uses explicit escalation language ("this is now
  urgent", "becoming critical", "needs to jump the queue", "top priority
  now", "escalating this") — not inferred from routine status updates.

## Tests (TDD, red → green)

- `tests/integration/test_v4_suggestions.py`:
  - `test_accept_update_entity_suggestion_sets_priority` — accepting a
    suggestion with `fields.priority="urgent"` sets
    `properties.priority="urgent"` on the target and records an `updated`
    event.
  - `test_accept_update_entity_suggestion_rejects_invalid_priority` — an
    invalid priority value (`"extreme"`) is rejected with 400 and the
    target is left unchanged.
- `tests/integration/test_v4_capture_extraction.py`:
  - `test_capture_progress_update_escalation_creates_priority_suggestion` —
    a `progress_update` decision with `fields.priority="urgent"` for a task
    with no existing priority creates exactly one `update_entity` suggestion
    with `payload.fields={"priority": "urgent"}`, and does not mutate the
    task's properties even at confidence 0.95.
  - `test_capture_progress_update_no_escalation_below_current_priority` — a
    decision with `fields.priority="low"` for a task whose current priority
    is `"high"` produces no suggestion (not an escalation).

Full backend suite green: 217 passed (was 213; +4 new).

## Acceptance criteria

- [x] `update_entity` suggestions can set `properties.priority`, validated
      against `low/medium/high/urgent`.
- [x] Capture reconciliation detects escalation language in progress
      updates and suggests a priority bump when it exceeds the entity's
      current priority.
- [x] Priority escalation suggestions are never auto-applied, regardless of
      confidence.
- [x] Suite green.

Not yet deployed.
