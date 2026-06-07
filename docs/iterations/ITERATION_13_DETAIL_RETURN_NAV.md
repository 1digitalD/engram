# Iteration 13 Contract

## Summary

- Iteration: 13
- Goal: make entity detail easier to exit by surfacing an explicit contextual return action
- Risk level: low

## User Problem

- Detail pages preserve the originating route in navigation state, but they do not surface that affordance in the UI.
- Users arriving from Today, Suggestions, Home, or a list screen have to rely on browser back behavior instead of an explicit in-product return path.

## Scope

- Routes / screens / handlers affected:
  - `ui/src/views/V4EntityDetail.jsx`
  - `ui/src/views/V4EntityScreens.module.css`
  - focused tests under `ui/src/views/V4EntityScreens.test.jsx`
- Data or API dependencies:
  - existing `location.state.from` behavior already used by delete/archive flows
- Write paths affected:
  - none

## Acceptance Criteria

- [x] Entity detail surfaces a contextual back action near the header.
- [x] The back action prefers the originating route when present and falls back to the entity collection route.
- [x] Existing detail edit and relationship flows continue to work.
- [x] Focused frontend tests pass.
- [x] Full frontend tests pass.
- [x] Frontend build passes.

## Non-Goals

- [ ] No breadcrumb system across the whole app.
- [ ] No attempt to infer deep navigation history beyond the preserved `from` route.
- [ ] No backend changes.

## Verification Plan

- Focused tests:
  - `ui/src/views/V4EntityScreens.test.jsx`
- Manual QA path:
  - open detail from Today and verify the back action returns there
  - open detail directly from a library list and verify the fallback collection target
- Broader validation:
  - `cd ui && npm test`
  - `cd ui && npm run build`

## Continuity Note

- Key decisions:
  - reuse the existing `from` route state rather than introducing new navigation state
  - keep the affordance lightweight and header-level instead of building a full breadcrumb component
- Files likely to change:
  - `ui/src/views/V4EntityDetail.jsx`
  - `ui/src/views/V4EntityScreens.module.css`
  - `ui/src/views/V4EntityScreens.test.jsx`
  - `EXECUTION-TRACKER.md`
- Main risks:
  - showing an unhelpful generic label when the route is unfamiliar
  - making the header busier without enough payoff
- Exact next step if interrupted:
  - finish the contextual back action and validate a Today-to-detail return flow
