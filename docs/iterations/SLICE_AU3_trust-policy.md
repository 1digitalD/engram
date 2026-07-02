# SLICE_AU3 — Activity update trust policy hardening

> **Activity Update v2**
> **Task id:** `au3-trust-policy`
> **Risk:** medium
> **Status:** Done

## Goal

Align direct activity-update extraction with V5 noise-reduction: new tasks become suggestions by default; remove silent 2-business-day follow-up on task progress notes without explicit dates. Preserve delegation cadence and explicit follow-up date auto-apply.

## Acceptance criteria

- Update content like "Also ask Mary for rollout notes" creates a pending `create_task` suggestion, not a surprise task (even at high extraction confidence).
- Explicit follow-up dates in update text still update `follow_up_at`.
- Task progress without explicit date does not change `follow_up_at` except delegation cadence rules.
- Delegation cadence tests still pass (`SLICE_C1_DELEGATION_CADENCE.md` behavior preserved).
- Update or remove AU0 baseline tests for auto-create and auto follow-up.
- `test_v4_suggestions.py` and `test_v4_today.py` pass.

## Validation commands

```
cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh \
  tests/integration/test_v4_activity_updates.py \
  tests/integration/test_v4_capture_extraction.py \
  tests/integration/test_v4_suggestions.py \
  tests/integration/test_v4_today.py
```

## Files affected

- `api/v4_entities.py`
- `tests/integration/test_v4_activity_updates.py`

## Results

**Tests:**
```
64 passed (activity_updates + suggestions + today)
test_activity_update_refreshes_delegation_follow_up_at passed
```

**Acceptance met:** [x] yes
