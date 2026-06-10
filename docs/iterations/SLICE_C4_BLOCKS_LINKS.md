# Slice C4 — Blocks links from updates

Status: DONE.

## Goal

Per `docs/V4_WORLD_MODEL_PLAN.md` Phase C, Slice C4: "waiting on X" / "blocked
by Y" statements in a captured note should produce a `blocks` link from the
blocking entity to the target task and set the target's status to
`blocked`/`waiting`, with `blocks` cycle detection enforced on every path
that creates or edits relationships.

## Changes

### Reconciliation (`services/v4_reconciliation.py`)
- `SYSTEM_PROMPT`'s `progress_update` action gains an optional
  `"blocked_by_id"` field: when `fields.status` is `"blocked"` or `"waiting"`
  and the update text names a specific blocker that matches an entity in the
  workspace catalog or the note's other candidates, the model returns that
  entity's id.

### Backend (`api/v4_entities.py`)
- New `_creates_blocks_cycle(source_entity_id, target_entity_id)`: BFS over
  existing `blocks` links from `target_entity_id` — returns `True` if
  `target` can already (transitively) reach `source`, i.e. adding
  `source --blocks--> target` would close a cycle. Also `True` for
  self-links.
- `_create_entity_link` now refuses (returns `None`, no-op) any `blocks` link
  that would create a cycle.
- `POST /entities/<id>/relationships` and `PATCH /relationships/<id>`
  (manual paths) now return `409 {"error": "relationship would create a
  blocks cycle"}` for the same case.
- `_apply_reconciliation_decision`'s `progress_update` branch: when a
  high-confidence status auto-applies to `"blocked"`/`"waiting"` and the
  decision carries a `blocked_by_id` that resolves to a different existing
  entity, a `blocks` link is created from the blocker to the target
  (`_create_entity_link`, cycle-checked), an `applied_changes` entry is
  recorded, and a `relationship_added` `EntityEvent` is written on the target
  with `source_note_id`.

## Tests (TDD, red → green)

- `tests/integration/test_v4_relationships.py`:
  - `test_blocks_cycle_rejected` — `A blocks B` then `B blocks A` → 409,
    "cycle" in error.
  - `test_blocks_cycle_rejected_via_update` — `A blocks B`, `B blocks C`,
    then `C related A`; PATCHing that last link's type to `"blocks"` → 409,
    "cycle" in error (would close `A→B→C→A`).
- `tests/integration/test_v4_capture_extraction.py`:
  - `test_capture_progress_update_blocked_status_creates_blocks_link` — a
    `progress_update` decision with `fields.status="blocked"` and
    `blocked_by_id` pointing at an existing task; asserts the target task's
    status becomes `"blocked"`, a `blocks` `EntityLink` is created from the
    blocker to the target, and `applied_changes` includes the
    `relationship_added` entry.

Full suite green: 210 passed (was 207; +3 new).

## Acceptance criteria

- [x] A fixture standup with a blocker statement yields a `blocks` link +
      `blocked` status.
- [x] Cyclic `blocks` links are rejected with a clear error on both create
      and update paths.
- [x] Suite green.

## Deploy

Per the plan, **Phase C deploys once after C4**. This slice's only schema
change is none (no migration needed — `blocks` was already a valid
`relationship_type`). Phases C1–C4 combined require migration
`scripts/migrations/002_add_app_settings.sql` (additive `app_settings`
table, Slice C1) to be applied to prod alongside the deploy.
