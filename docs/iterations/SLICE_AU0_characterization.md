# SLICE_AU0 — Activity update v2 characterization and policy lock

> **Activity Update v2**
> **Task id:** `au0-characterization`
> **Risk:** low
> **Status:** Done

## Goal

Freeze current behavior with tests before changing semantics. Document the V5 regression (capture instead of Add update), backend gaps (embed, provenance, trust policy), and capture `thread_id` non-semantics. No production behavior changes in this slice unless a test fixture is broken.

## Acceptance criteria

- `tests/integration/test_v4_activity_updates.py` has baseline tests (prefixed or clearly named) documenting:
  - direct POST does not queue embed job for the update note (AU1 will fix);
  - direct `activity_update_added` event lacks `source_note_id` (AU2 will fix);
  - task update without explicit date auto-sets 2-business-day follow-up (AU3 will fix);
  - high-confidence extracted task is auto-created, not suggested (AU3 will fix);
  - bookkeeping `updated` event is written alongside `activity_update_added` (AU2 will address narration).
- `tests/integration/test_v4_capture_extraction.py` has baseline test: capture with `thread_id` in body does not create activity updates.
- `ui/src/views/V5ThreadDetail.test.jsx` documents baseline: Capture FAB opens generic capture with thread attached; `activityUpdates.create` is not called.
- `ui/src/views/V5CaptureSheet.test.jsx` unchanged or extended only if needed for baseline documentation.
- Narrow validators pass (see below).

## Validation commands

```
cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_activity_updates.py tests/integration/test_v4_capture_extraction.py
cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test -- V5ThreadDetail V5CaptureSheet
```

## Files affected

- `tests/integration/test_v4_activity_updates.py`
- `tests/integration/test_v4_capture_extraction.py`
- `ui/src/views/V5ThreadDetail.test.jsx`

## Slice doc references

- **Spec:** `docs/iterations/ACTIVITY_UPDATE_V2_SPEC.md`
- **Plan:** `docs/iterations/ACTIVITY_UPDATE_V2_IMPLEMENTATION_PLAN.md`
- **Continuity:** `EXECUTION-TRACKER.md`

## Results (filled in on completion)

**Tests:**
```
76 passed (test_v4_activity_updates.py + test_v4_capture_extraction.py)
20 passed (V5ThreadDetail + V5CaptureSheet)
```

**Acceptance met:** [x] yes
