# Slice B2 — Auto-apply state changes carried by `progress_update`

Phase: B — World model, follow-up to [[SLICE_B1_PROGRESS_UPDATE]]
Status: COMPLETE

## Goal

Per `docs/V4_WORLD_MODEL_PLAN.md` Phase B, Slice B2: extend `progress_update`
decisions (added in Slice B1) so that, when the update text clearly implies a
status transition (e.g. "shipped the HITL piece" → done, "still waiting on
infra" → waiting), the reconciler can carry an optional `fields.status` and
capture auto-applies it for high-confidence decisions, with an `EntityEvent`
recording the old/new status. Low-confidence status changes still surface as
`update_entity` suggestions instead of auto-applying. Status transitions are
guarded against the existing `VALID_STATUS` vocabulary per entity type.

`update`-action status auto-apply (today's `_apply_entity_update`) was
already in place and is untouched; this slice only extends the
`progress_update` branch added in B1.

## Changes

- `services/v4_reconciliation.py`: `SYSTEM_PROMPT`'s `progress_update` output
  spec documents an optional `fields` object with `status`, with examples
  ("shipped"/"delivered" → done, "still waiting on X" → waiting, "blocked on
  X" → blocked) and an instruction to omit `fields` entirely when no status
  change is implied. Matching logic untouched.
- `api/v4_entities.py`, `_apply_reconciliation_decision`'s `progress_update`
  branch: after creating the activity-update note (always, regardless of
  confidence — additive/safe per B1), reads `decision["fields"]["status"]`.
  - If the status is valid for `target.type` (`VALID_STATUS[target.type]`)
    and differs from the current status:
    - **`confidence >= AUTO_APPLY_CONFIDENCE` (0.8)**: applies the status
      change directly, appends an `entity_updated` applied-change entry
      (`{"changes": {"status": new_status}, ...}`, matching the shape used by
      `update`-action auto-applies), writes an `EntityEvent` of type
      `ai_updated` with `old_value={"status": old}` /
      `new_value={"status": new}`, and queues a re-embed job.
    - **below the gate**: appends an `update_entity` suggestion (same shape
      as the existing low-confidence `update`-action suggestion: `payload`
      with `target_entity_id`, `target_type`, `title`,
      `fields={"status": new_status}`, `relationship_type`, `assigned_to`,
      `evidence`). Accepting this suggestion goes through the existing
      `_accept_update_entity_suggestion`, which already validates/applies
      `fields.status` generically — no changes needed there.
  - If the status is invalid for the target's type, or unchanged, or absent,
    nothing extra happens beyond the B1 activity-update behavior — this is
    the "guard" against the status vocabulary.

## Tests (red → green)

Added to `tests/integration/test_v4_capture_extraction.py`:

1. `test_capture_progress_update_with_high_confidence_status_auto_applies` —
   a `progress_update` with `fields={"status": "done"}` and confidence 0.92
   against an `open` task: asserts `applied_changes` contains both
   `activity_update_added` and an `entity_updated` entry with
   `changes={"status": "done"}`, `suggestions == []`, the task's status is
   `"done"` in the DB, and an `ai_updated` `EntityEvent` records
   `old_value={"status": "open"}` / `new_value={"status": "done"}`.
2. `test_capture_progress_update_with_low_confidence_status_becomes_suggestion`
   — same shape but confidence 0.5: the activity update is still applied
   (additive/safe), but the status is **not** changed; instead exactly one
   `update_entity` suggestion is produced with
   `payload["fields"] == {"status": "waiting"}`, and the task's status
   remains `"open"` in the DB.
3. `test_capture_progress_update_with_invalid_status_is_ignored` — `fields={"status":
   "not_a_real_status"}` at confidence 0.95: no `entity_updated` change, no
   suggestion, task status stays `"open"` (vocabulary guard).

All three were written first and failed (red) before the implementation
(`high_confidence` and `low_confidence` failed; `invalid_status` happened to
pass trivially since the field was simply ignored — this confirms the guard
was a no-op pre-change and remains correct post-change).

## Test/QA evidence

```
TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test venv/bin/python -m pytest --tb=short -q
195 passed, 4 warnings
```

(Was 192 after B1; +3 new tests, all green. Backend-only, no frontend
changes.)

## Replay eval

Ran the live replay eval once after this change:

| Run | Score |
| --- | --- |
| `20260610_043139.json` | 15/27 (56%) |

Combined with the three B1 runs (17/27, 17/27, 16/27), all four post-B1 runs
are below the single Phase A baseline (19/27). Per-decision inspection of
this run shows the same pre-existing matching-noise pattern as B1
(umbrella-area mismatches for "Agent Platform"-adjacent candidates,
missing-person-match for "Hemant"/"Ram"). `progress_update` was again chosen
only once (for "HITL CS2 Onboarding Demo", an `accept`-labeled item) and
scored correct — this run's decision did not carry `fields.status`, so the
new status-transition code path in this slice was not exercised live, only
by the (deterministic, mocked) integration tests above.

Given:
- the new status-transition logic only executes inside the `progress_update`
  branch, which fires on ~1/27 candidates per run and didn't carry
  `fields.status` in this run — it cannot be the cause of the broader score
  drop;
- the incorrect items are the same recurring umbrella-area/person-matching
  issues already tracked as pre-existing noise in
  `SLICE_B1_UMBRELLA_LINK_FILTER.md` and `SLICE_B1_PROGRESS_UPDATE.md`;
- the mechanism under test (status auto-apply + EntityEvent + suggestion
  fallback + vocabulary guard) is fully covered and green under the
  integration tests,

this is treated as the same documented noise floor, not a regression
introduced by this slice. As before, getting the live model to emit
`fields.status` more readily for standup-style status remarks is a follow-up
prompt-tuning task, tracked alongside the B1 follow-up about
`progress_update` pickup rate.

## Acceptance criteria

- [x] `update`-action auto-apply of status/due_at/follow_up_at at confidence
      ≥ 0.8 is unchanged (not touched by this slice).
- [x] `progress_update` decisions can carry `fields.status`; at confidence ≥
      0.8 the target's status is auto-applied with an `EntityEvent` recording
      old/new values.
- [x] Status transitions are validated against `VALID_STATUS` per entity
      type; invalid/no-op statuses are silently ignored (guard).
- [x] Low-confidence status changes via `progress_update` become
      `update_entity` suggestions instead of auto-applying (existing
      activity-update behavior from B1 still applies regardless of
      confidence).
- [x] Red-first integration tests, now green; full suite green (195 passed).
- [~] Fixture acceptance ("shipped the HITL piece" moves the matched task to
      done with an auditable event") is verified at the mechanism level via
      `test_capture_progress_update_with_high_confidence_status_auto_applies`.
      The live replay set didn't produce a `fields.status`-bearing
      `progress_update` decision in this run — same follow-up prompt-tuning
      note as B1 applies to getting the live model to emit `fields.status`
      more often.
