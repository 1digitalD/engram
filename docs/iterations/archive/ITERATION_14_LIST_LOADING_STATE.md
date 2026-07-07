# Iteration 14 Contract

## Summary

- Iteration: 14
- Goal: prevent false empty states on entity list screens by adding an explicit loading state
- Risk level: low

## User Problem

- Entity list screens render empty-state copy immediately while their initial fetch is still in flight.
- That makes populated lists look empty for a moment and likely caused the `/areas` runtime confusion during live QA.

## Scope

- Routes / screens / handlers affected:
  - `ui/src/views/V4EntityList.jsx`
  - focused tests under `ui/src/views/V4EntityScreens.test.jsx`
- Data or API dependencies:
  - existing `/api/v4/entities`
- Write paths affected:
  - none

## Acceptance Criteria

- [x] Entity lists show an explicit loading state during the initial fetch.
- [x] Empty-state copy only appears after the fetch has resolved.
- [x] Existing create flows continue to work.
- [x] Focused frontend tests pass.
- [x] Full frontend tests pass.
- [x] Frontend build passes.

## Non-Goals

- [ ] No skeleton loading system across the whole app.
- [ ] No backend changes.
- [ ] No redesign of list filtering or sorting.

## Verification Plan

- Focused tests:
  - `ui/src/views/V4EntityScreens.test.jsx`
- Manual QA path:
  - open a populated list route and verify it no longer flashes a false empty state
  - open an actually empty list route and confirm the empty state still appears after loading
- Broader validation:
  - `cd ui && npm test`
  - `cd ui && npm run build`

## Continuity Note

- Key decisions:
  - split fetch loading from create loading so list fetch state does not interfere with the create button
  - keep the loading surface as simple text rather than introducing placeholder cards
- Files likely to change:
  - `ui/src/views/V4EntityList.jsx`
  - `ui/src/views/V4EntityScreens.test.jsx`
  - `EXECUTION-TRACKER.md`
- Main risks:
  - accidentally blocking create flows with the wrong loading flag
  - leaving stale loading state on list-fetch errors
- Exact next step if interrupted:
  - finish explicit list loading state and validate the area-list regression path
