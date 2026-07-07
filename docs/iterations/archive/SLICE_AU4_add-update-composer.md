# SLICE_AU4 — V5 AddUpdateComposer

> **Activity Update v2**
> **Task id:** `au4-add-update-composer`
> **Risk:** low
> **Status:** Done

## Goal

Restore entity-scoped Add update on V5 thread detail without using generic capture. Minimal inline composer; FAB remains for broad capture elsewhere.

## Acceptance criteria

- Project/task/area detail shows Add update composer (compact, expandable).
- Submit calls `v4API.activityUpdates.create(entity.id, content)` — not `openCapture`.
- After success: clears draft, reloads detail/events/canonical, refreshes summary context.
- Empty update cannot submit; errors visible and retryable.
- Test verifies `activityUpdates.create` called and `openCapture` not used for Add update.
- Capture FAB behavior unchanged; Add update is separate control.
- `npm test -- V5ThreadDetail` and `npm run build` pass.

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

**Tests:**
```
15 passed (V5ThreadDetail.test.jsx)
vite build succeeded
```

**Manual smoke:**
Open project/task/area detail → Write update → Save update → verify reload.

**Acceptance met:** [x] yes
