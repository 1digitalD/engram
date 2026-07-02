# SLICE_AU1 — Direct activity update embed and summary queue

> **Activity Update v2**
> **Task id:** `au1-embed-summary`
> **Risk:** low
> **Status:** Done

## Goal

Make direct activity-update notes participate in search/Ask/Recall and trigger target summary refresh using existing job patterns. Smallest backend-only change; no UI yet.

## Acceptance criteria

- POST direct activity update queues an embed job for the update note (`reason` includes `activity_update`).
- POST direct activity update queues or triggers target summarization via `queue_summarize_if_needed` (assert job row or existing helper side effect in tests).
- Existing activity update retrieval and POST response shape remain backward compatible (`data`, `target`, `extracted`, `suggestions`).
- Remove or update AU0 baseline test for missing embed job.
- AU0 characterization tests for unrelated behavior still pass.

## Validation commands

```
cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_activity_updates.py tests/integration/test_v4_timeline.py
```

## Files affected

- `api/v4_entities.py` (or extracted helper if introduced minimally)
- `tests/integration/test_v4_activity_updates.py`

## Results (filled in on completion)

**Tests:**
```
22 passed in 1.09s (tests/integration/test_v4_activity_updates.py)
```

**Acceptance met:** [x] yes
