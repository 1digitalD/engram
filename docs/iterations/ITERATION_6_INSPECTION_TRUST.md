# Iteration 6 Contract

## Summary

- Iteration: 6
- Goal: expose enough provenance and recent history that users can trust AI-linked changes and review decisions without leaving the current surface
- Risk level: medium

## User Problem

- The v4 UI now exposes stronger home, review, capture, planner, and project surfaces, but it still asks users to trust suggestions and entity state with too little inspection context.
- Users need to see why something was suggested, how confident the system was, and what changed recently before they accept risky work or assume a page is current.

## Scope

- Routes / screens / handlers affected:
  - `ui/src/views/V4EntityDetail.jsx`
  - `ui/src/views/V4Suggestions.jsx`
  - related CSS modules and focused tests
- Data or API dependencies:
  - existing `/api/v4/entities/:id/events`
  - existing `/api/v4/entities/:id/detail`
  - existing `/api/v4/suggestions`
- Write paths affected:
  - none beyond the existing suggestion accept/dismiss/edit and entity update flows

## Acceptance Criteria

- [x] Entity detail exposes a lightweight inspection panel using existing detail + events data.
- [x] The inspection surface makes AI status/confidence and recent entity history visible without navigating away.
- [x] Suggestion review surfaces confidence and provenance context more explicitly.
- [x] Existing edit/review flows continue to work unchanged.
- [x] Focused frontend tests pass.
- [x] Full frontend tests pass.
- [x] Frontend build passes.

## Non-Goals

- [ ] No backend schema or API shape changes.
- [ ] No full audit-log product or advanced diff viewer.
- [ ] No new suggestion workflow beyond clearer inspection context.

## Verification Plan

- Focused tests:
  - `ui/src/views/V4EntityScreens.test.jsx`
  - `ui/src/views/V4Suggestions.test.jsx`
- Manual QA path:
  - open a note, task, and project detail
  - verify AI status/confidence and recent history render clearly
  - open Suggestions and confirm confidence/provenance context is visible before acting
- Broader validation:
  - `cd ui && npm test`
  - `cd ui && npm run build`

## Continuity Note

- Key decisions:
  - keep the slice frontend-only and reuse existing trust/provenance APIs
  - favor compact inspection context over adding a separate audit route
- Files likely to change:
  - `ui/src/views/V4EntityDetail.jsx`
  - `ui/src/views/V4EntityScreens.module.css`
  - `ui/src/views/V4Suggestions.jsx`
  - `ui/src/views/V4Suggestions.module.css`
  - focused frontend tests
- Main risks:
  - cluttering already-dense detail screens
  - showing raw low-signal event payloads instead of useful trust cues
- Exact next step if interrupted:
  - finish the compact inspection panel on entity detail, then wire suggestion confidence/provenance presentation and update focused tests
