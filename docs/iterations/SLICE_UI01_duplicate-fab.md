# SLICE_UI01 — Remove duplicate Capture FAB

> **V5 Productivity & Trust**
> **Task id:** `ui-01-duplicate-fab`
> **Risk:** low
> **Status:** Done (overseer canary, 2026-07-02)

## Goal

Entity detail shows two Capture FABs (App.jsx global + V5ThreadDetail local). Keep one global FAB; CaptureContext still attaches current entity.

## Acceptance criteria

- Exactly one capture entry point on `/tasks/:id`, `/projects/:id`, etc.
- Capture from entity route still sends thread_id / default attachment.
- `npm test -- V5ThreadDetail App` and `npm run build` pass.

## Validation commands

```
cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test -- V5ThreadDetail App
cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm run build
```

## Files affected

- `ui/src/views/V5ThreadDetail.jsx`
- `ui/src/views/V5ThreadDetail.test.jsx` (if assertion added)

## Results

<!-- Loopsmith / overseer fills in on completion -->

**Acceptance met:** [x] yes

**Commit:** pending overseer commit for UI-01 code change
