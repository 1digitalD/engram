# SLICE_UI02 — Add update outcome panel

> **Task id:** `ui-02-update-outcome-panel`
> **Risk:** medium
> **Status:** Pending

## Goal

Show applied/suggested outcomes after `activityUpdates.create` instead of silently reloading.

## Acceptance criteria

- Outcome panel after successful save (counts, follow-up applied, suggestion titles).
- Details chips reflect updated follow_up_at after reload.
- Tests with mocked suggestions in API response.

## Validation commands

```
cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test -- V5ThreadDetail
cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm run build
```

## Files affected

- `ui/src/views/V5ThreadDetail.jsx`
- `ui/src/views/V5ThreadDetail.test.jsx`
- `ui/src/styles/v5.module.css`

## Results

**Acceptance met:** [ ] yes / [ ] no
