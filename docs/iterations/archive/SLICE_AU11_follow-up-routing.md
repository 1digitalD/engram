# SLICE_AU11 — Follow-up routing for spin-off work

> **Task id:** `au11-follow-up-routing`
> **Risk:** medium
> **Status:** Pending

## Goal

When update closes task and introduces new work, follow-up dates belong on the suggestion payload, not the closing task.

## Acceptance criteria

- Done/cancelled target does not get follow_up_at when spin-off carries the date.
- Open-task explicit follow-up unchanged.
- Integration test: done + security review task + follow up next week.

## Validation commands

```
cd /Volumes/lex1t/dev/shared/repos/engram && TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest tests/integration/test_v4_activity_updates.py -q
```

## Files affected

- `services/v4_extraction.py`
- `api/v4_entities.py`
- `tests/integration/test_v4_activity_updates.py`

## Results

**Acceptance met:** [ ] yes / [ ] no
