# SLICE_AU6 — Generic capture attachment cleanup (deferred)

> **Activity Update v2**
> **Task id:** `au6-capture-cleanup`
> **Risk:** medium
> **Status:** Done

## Goal

Clarify that attached generic capture is context/relationship, not an entity update. Optionally adjust post-capture `related` link copy or semantics.

## Acceptance criteria

- Generic capture still works from Now/Threads/Recall.
- Entity detail Add update is the preferred path for progress updates.
- Attachment copy does not imply automatic activity update.
- `npm test -- V5CaptureSheet V5ThreadDetail` passes.

## Validation commands

```
cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test -- V5CaptureSheet V5ThreadDetail V5Recall
```

## Files affected

- `ui/src/views/V5CaptureSheet.jsx`
- `ui/src/views/V5CaptureSheet.test.jsx`

## Results

**Tests:**
```
8 passed (V5CaptureSheet), 15 passed (V5ThreadDetail), V5Recall passed
```

**Copy changes:** thread selector labeled "Thread context"; attached options suffixed "(related link)"; `CAPTURE_ATTACHMENT_HINT` shown when a thread is selected.

**Acceptance met:** [x] yes
