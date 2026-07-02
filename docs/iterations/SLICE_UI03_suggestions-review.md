# SLICE_UI03 — V5 suggestions review sheet

> **Task id:** `ui-03-suggestions-review`
> **Risk:** medium
> **Status:** Pending

## Goal

Restore pending suggestion review UI; badge from summary.suggestions_count; capture toast link when suggested > 0.

## Acceptance criteria

- V5ReviewSheet lists pending suggestions; accept/dismiss wired.
- Top bar badge when suggestions_count > 0.
- Capture toast review link when applicable.
- Tests + test_v4_suggestions.py pass.

## Validation commands

```
cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test -- V5ReviewSheet App TopBar V5CaptureSheet
cd /Volumes/lex1t/dev/shared/repos/engram && TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest tests/integration/test_v4_suggestions.py -q
cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm run build
```

## Files affected

- `ui/src/views/V5ReviewSheet.jsx` (new)
- `ui/src/App.jsx`
- `ui/src/components/TopBar.jsx`
- `ui/src/views/V5CaptureSheet.jsx`

## Results

**Acceptance met:** [ ] yes / [ ] no
