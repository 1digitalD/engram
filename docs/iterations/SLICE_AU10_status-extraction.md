# SLICE_AU10 — Activity update status extraction

> **Task id:** `au10-status-extraction`
> **Risk:** medium
> **Status:** Pending

## Goal

Port capture progress_update status semantics to direct Add update path. Extend lightweight extractor + handler; suggestions for uncertain status; tasks remain suggestions only.

## Acceptance criteria

- Extractor returns optional status.
- Explicit done language can close task (tested with mock extraction).
- No silent auto-create of new tasks.
- test_v4_activity_updates.py passes with new cases.

## Validation commands

```
cd /Volumes/lex1t/dev/shared/repos/engram && TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest tests/integration/test_v4_activity_updates.py -q
cd /Volumes/lex1t/dev/shared/repos/engram && TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest tests/integration/test_v4_suggestions.py -q
```

## Files affected

- `services/v4_extraction.py`
- `api/v4_entities.py`
- `tests/integration/test_v4_activity_updates.py`

## Results

**Acceptance met:** [ ] yes / [ ] no
