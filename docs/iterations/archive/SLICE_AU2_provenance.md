# SLICE_AU2 — Activity update provenance and timeline hygiene

> **Activity Update v2**
> **Task id:** `au2-provenance`
> **Risk:** low
> **Status:** Done

## Goal

Set `source_note_id` on direct `activity_update_added` events (update note cites itself). Stop bookkeeping `updated_at` bumps from narrating in timeline, without removing audit events if still needed for revert/changelog.

## Acceptance criteria

- Direct POST sets `source_note_id=note.id` on `activity_update_added` for the target.
- Timeline/entity events for activity updates do not surface spurious "Updated updated at" narration to users (filter in narration, event query, or stop writing narratable `updated` for this path — pick smallest fix).
- Capture-derived progress updates still preserve `source_note_id` pointing at capture note.
- Update or remove AU0 baseline tests for missing `source_note_id` and bookkeeping narration.
- Timeline integration tests pass.

## Validation commands

```
cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_activity_updates.py tests/integration/test_v4_timeline.py tests/integration/test_v4_entity_detail.py
```

## Files affected

- `api/v4_entities.py`
- `tests/integration/test_v4_activity_updates.py`

## Results

**Tests:**
```
25 passed (tests/integration/test_v4_activity_updates.py)
```

**Acceptance met:** [x] yes
