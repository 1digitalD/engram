# Slice Post-Plan — Low-Value Task Suppression

Status: IMPLEMENTED (merged via SQ-09 tentative task gate).

## Goal

Reduce low-value task creation during capture extraction without suppressing
concrete follow-ups. The change makes the extractor prompt more conservative
about tentative wording and adds a narrow runtime gate so hedged task phrasing
does not clutter the review queue.

## Changes

- `services/v4_extraction.py`
  - Reworded the task extraction instructions to prefer concrete, owner-bearing
    next steps over tentative language.
  - Explicitly asks the model to avoid tentative phrasing like "maybe",
    "possibly", "could", and "think about" when emitting task candidates.
- `api/v4_entities.py`
  - Added a small capture gate for task candidates that start with obviously
    tentative phrasing.
  - Low-confidence tentative tasks are dropped before they can become review
    suggestions or auto-created entities.
- `tests/integration/test_v4_capture_extraction.py`
  - Changed the low-confidence task test to assert that "Maybe follow up" is
    suppressed entirely.
  - Existing concrete low-confidence task coverage still verifies that useful
    follow-ups like "Follow up with Henry" continue to surface for review.

## Validation

- `PYTHONPATH=. TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test /Volumes/lex1t/dev/shared/repos/engram/venv/bin/pytest tests/integration/test_v4_capture_extraction.py -q`
  - Passed: 45 tests
- `PYTHONPATH=. /Volumes/lex1t/dev/shared/repos/engram/venv/bin/python -m py_compile api/v4_entities.py services/v4_extraction.py tests/integration/test_v4_capture_extraction.py`
  - Passed
- Full backend suite:
  - Currently surfaces three unrelated semantic-search failures in
    `tests/integration/test_v4_search.py`
  - Those failures are outside this slice and need follow-up before merge

## Notes

- The change is intentionally narrow. It suppresses tentative task phrasing,
  but keeps concrete low-confidence tasks eligible for review.
- No deploy or schema change is required.
