# Slice B3 — Capture changelog + one-click undo

Status: DONE. Phase B (Progress propagation + undo) complete.

## Goal

Per `docs/V4_WORLD_MODEL_PLAN.md` Phase B, Slice B3: give the user visibility into
everything the agent auto-applied during a capture, and a one-click way to revert
any single change. This is the safety valve that makes "aggressive auto-apply"
(B1/B2) trustworthy.

## Changes

### Schema (additive)
- `entity_events` gains two nullable columns:
  - `source_note_id` (FK → `entities.id`, `ON DELETE SET NULL`) — links an event
    back to the capture (note) that produced it.
  - `reverted_at` (timestamptz, nullable) — set when a change has been undone.
- New `event_type` enum value: `'reverted'`.
- New index `entity_events_source_note_idx (source_note_id, created_at ASC)`.
- `docs/SCHEMA.sql` updated (used by the test DB bootstrap).
- `scripts/migrations/001_add_event_revert_fields.sql` — idempotent additive
  migration for the prod DB (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, constraint
  drop/recreate, `CREATE INDEX IF NOT EXISTS`). Not yet applied to prod — apply
  before/with the Phase B deploy.

### Backend (`api/v4_entities.py`, `models.py`)
- `EntityEvent` model: added `source_note_id`, `reverted_at` columns and fields in
  `to_dict()`. `Entity.events` and `EntityEvent.entity` relationships now specify
  `foreign_keys` explicitly (two FKs to `entities` now exist).
- `_write_event(...)` takes an optional `source_note_id` kwarg. Every
  `agent:v4-capture` event written during `_reconcile_capture_candidates` /
  `_apply_reconciliation_decision` / `_apply_entity_update` /
  `_link_task_to_note_projects` / `_apply_assignee_and_record` /
  `_create_activity_update_note` (capture path) now stamps `source_note_id` with
  the capturing note's id.
- `_apply_entity_update`: now records `old_value` (previous status/due_at/
  follow_up_at) on its `ai_updated` event — previously only `new_value` was
  recorded, which made this change un-revertible.
- New `GET /api/v4/entities/<id>/capture-changes`: returns all
  `agent:v4-capture` events with `source_note_id == id` and
  `event_type in {created, ai_updated, relationship_added, activity_update_added}`,
  oldest first.
- New `POST /api/v4/events/<id>/revert`: inverts one applied change by event type:
  - `ai_updated` → restores `status`/`title`/`due_at`/`follow_up_at` from
    `old_value` (status revalidated against `VALID_STATUS`).
  - `created` → sets the created entity's `lifecycle = "deleted"`.
  - `activity_update_added` → sets the activity-update note's
    `lifecycle = "archived"` ("archival").
  - `relationship_added` → deletes the `EntityLink` referenced by `new_value.id`.
  - Any other event type → 400 "cannot revert event of type: ...".
  Each revert writes its own `reverted` `EntityEvent` (old/new value of the
  revert itself) and sets `reverted_at` on the original event. Reverting an
  already-reverted event returns 409. Unknown event id → 404.

### Frontend (`ui/src/api/v4Client.js`, `ui/src/views/V4EntityDetail.jsx`)
- `v4API.entities.captureChanges(id)` and `v4API.events.revert(id)`.
- New `CaptureChangesPanel` — a "What the agent did" section rendered on note
  detail pages. Lists capture-changes events (reusing the existing `eventTitle`/
  `eventReason` formatting), with a **Revert** button per row; reverted rows show
  a "Reverted" chip instead. Hidden entirely if there are no capture changes for
  the note.

## Tests (TDD, red → green)

Added to `tests/integration/test_v4_capture_extraction.py`:
- `test_capture_changes_lists_agent_applied_changes_for_note`
- `test_revert_ai_updated_status_change_restores_old_status` (incl. double-revert
  → 409)
- `test_revert_activity_update_archives_note`
- `test_revert_relationship_added_removes_link`
- `test_revert_created_entity_marks_lifecycle_deleted`
- `test_revert_unknown_event_returns_404`

Added to `ui/src/views/V4EntityScreens.test.jsx`:
- "shows what the agent did on a note and allows reverting a change"

## QA evidence

- Backend: `pytest -q` → **201 passed** (was 195; +6 new).
- Frontend: `npm test` → **43 passed** (was 42; +1 new); `npm run build` → succeeds.
- Live manual QA against the test DB (port 5433) via a scratch Flask instance:
  created a task, applied a `progress_update` decision (status `open` → `done` +
  activity-update note), then:
  - `GET /entities/<note_id>/capture-changes` → returns the `activity_update_added`
    and `ai_updated` events with `source_note_id` set and `reverted_at: null`.
  - `POST /events/<ai_updated_event_id>/revert` → 200, task status back to `open`,
    `reverted_at` set, new `reverted` EntityEvent recorded
    (`old_value={"status":"done"}`, `new_value={"status":"open"}`).
  - Repeating the revert → 409 "event already reverted".

This slice does not touch extraction or reconciliation prompts/logic, so the
replay harness is not re-run (merge gate item 4 only applies to slices touching
extraction/reconciliation).

## Acceptance criteria

- [x] Every auto-applied change type from B1/B2 (`created`, `ai_updated`,
      `relationship_added`, `activity_update_added`) can be reverted in one click.
- [x] The revert is itself event-logged (`reverted` EntityEvent with old/new
      values).
- [x] Suite + UI tests green.

**Phase B (Progress propagation + undo) is now complete.** Remaining for the
Phase B deploy step: apply `scripts/migrations/001_add_event_revert_fields.sql`
to prod (after a `pg_dump` snapshot), then `./scripts/engram-deploy.sh` and smoke
test per the plan's deploy cadence.
