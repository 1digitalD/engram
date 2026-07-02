# SLICE_AU8 — Capture thread_id extraction bias

> **Activity Update v2 follow-up**
> **Task id:** `au8-capture-thread-bias`
> **Risk:** low
> **Status:** complete

## Goal

When generic capture is attached to a thread, pass `thread_id` into extraction and reconciliation as context bias so progress remarks match the current entity. This does not create activity updates — Add update remains the explicit path.

## Acceptance criteria

- `POST /api/v4/capture` with `thread_id` passes it through extraction and reconciliation.
- Extraction prompt includes a THREAD_CONTEXT block for the attached entity.
- Reconciliation boosts the attached entity into candidate matches when types align.
- Capture with `thread_id` still does not auto-create activity updates.
- Skipped progress updates still do not auto-apply status (regression from ship gate).
- Tests pass.

## Validation commands

```
cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_capture_extraction.py tests/unit/test_v4_reconciliation.py
```

## Files affected

- `api/v4_entities.py`
- `services/v4_extraction.py`
- `services/v4_reconciliation.py`
- `tests/integration/test_v4_capture_extraction.py`
- `tests/unit/test_v4_reconciliation.py`

## Results (filled in on completion)

**Acceptance met:** [x] yes / [ ] no

- `thread_id` flows capture → extraction (`thread_entity`) → reconciliation (`thread_id` bias).
- `THREAD_CONTEXT` block added to extraction prompt.
- Reconciliation boosts attached entity (score 0.95) when candidate type matches.
- Capture with `thread_id` still does not create activity updates.
- 62 tests in capture extraction + reconciliation suites pass.
