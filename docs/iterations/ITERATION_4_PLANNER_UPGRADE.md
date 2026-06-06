# Iteration 4 Contract

## Summary

- Iteration: 4
- Goal: upgrade `Today` from a bucketed execution feed into a clearer planning surface
- Risk level: medium

## User Problem

- The current Today page exposes useful buckets but still requires too much scanning and decision-making.
- Users need clearer priority cues and a better sense of what to focus on now versus what should be rescheduled or monitored.

## Scope

- Routes / screens / handlers affected:
  - `ui/src/views/V4Today.jsx`
  - `ui/src/views/V4Today.module.css`
  - `ui/src/views/V4Today.test.jsx`
- Data or API dependencies:
  - existing `/api/v4/today`
- Write paths affected:
  - existing task/entity quick updates only

## Slice Intent

- Add a derived `Focus now` section near the top.
- Add clearer reason labels so users can see why an item is on the page.
- Add a compact planning summary without creating stored planner state.
- Keep existing quick status/date updates intact.

## Acceptance Criteria

- [x] Today surfaces a clear `Focus now` section derived from current urgency buckets.
- [x] Rows show concise reason cues such as overdue, due today, follow-up, blocked, or waiting.
- [x] Existing Today sections remain available, but the page is easier to scan for next action.
- [x] No backend changes or stored planner state are introduced.
- [x] Focused frontend tests pass.
- [x] Frontend build passes.

## Non-Goals

- [ ] No explicit persisted focus list.
- [ ] No calendar integration.
- [ ] No new endpoints.
- [ ] No project-workspace redesign.

## Verification Plan

- Focused tests:
  - `ui/src/views/V4Today.test.jsx`
- Manual QA path:
  - load Today
  - verify focus items and reason labels
  - quick update status and dates
- Broader validation if needed:
  - `cd ui && npm test`
  - `cd ui && npm run build`

## Continuity Note

- Key decisions:
  - use derived focus logic only
  - preserve Today as an execution surface while reducing scan cost
- Files likely to change:
  - `ui/src/views/V4Today.jsx`
  - `ui/src/views/V4Today.module.css`
  - `ui/src/views/V4Today.test.jsx`
- Main risks:
  - duplicating items between focus and detailed sections in confusing ways
  - adding too many visual cues and making the page noisier
- Exact next step if interrupted:
  - run a live manual QA pass on Home and Today, then lock the next slice for Project Workspace
