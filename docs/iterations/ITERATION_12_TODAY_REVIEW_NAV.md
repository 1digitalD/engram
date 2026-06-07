# Iteration 12 Contract

## Summary

- Iteration: 12
- Goal: tighten the Today-to-review navigation path around pending suggestions
- Risk level: low

## User Problem

- The Today screen still showed pending suggestions as flat generic links into the Suggestions route.
- That made review work feel disconnected from the source note context, even after the dedicated Suggestions grouping pass.

## Scope

- Routes / screens / handlers affected:
  - `ui/src/views/V4Today.jsx`
  - `ui/src/views/V4Today.module.css`
  - focused tests under `ui/src/views/V4Today.test.jsx`
- Data or API dependencies:
  - existing `/api/v4/today`
  - existing `/api/v4/entities/:id`
- Write paths affected:
  - none

## Acceptance Criteria

- [x] Today groups pending suggestions around source notes where possible.
- [x] Today provides direct paths to open the source note and to review in Suggestions.
- [x] Existing Today task and note flows continue to work.
- [x] Focused frontend tests pass.
- [x] Full frontend tests pass.
- [x] Frontend build passes.

## Non-Goals

- [ ] No backend schema or endpoint changes.
- [ ] No accept/dismiss actions embedded directly into Today.
- [ ] No attempt to replace the full Suggestions review route.

## Verification Plan

- Focused tests:
  - `ui/src/views/V4Today.test.jsx`
- Manual QA path:
  - open Today with pending suggestions and confirm source-note context is visible
  - verify both “open source note” and “review in Suggestions” paths
- Broader validation:
  - `cd ui && npm test`
  - `cd ui && npm run build`

## Continuity Note

- Key decisions:
  - reuse the existing source note entity fetch pattern already used on Suggestions
  - improve Today as a navigation surface, not as a second full review tool
- Files likely to change:
  - `ui/src/views/V4Today.jsx`
  - `ui/src/views/V4Today.module.css`
  - `ui/src/views/V4Today.test.jsx`
  - `EXECUTION-TRACKER.md`
- Main risks:
  - duplicating too much of the Suggestions screen
  - making Today too dense if note excerpts are too large
- Exact next step if interrupted:
  - finish grouped suggestion rendering on Today and validate the new source-note navigation links
