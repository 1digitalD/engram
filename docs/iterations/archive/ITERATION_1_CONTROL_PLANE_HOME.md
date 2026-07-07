# Iteration 1 Contract

## Summary

- Iteration: 1
- Goal: make the landing route a real control-plane home screen that tells the user what matters now and where to go next
- Risk level: medium

## User Problem

- The current default landing page is Inbox, which is strong for capture but weak for orientation.
- Users need a clear starting surface that summarizes review work, today's pressure, stuck work, active projects, and recent captures in one place.

## Scope

- Routes / screens / handlers affected:
  - `ui/src/App.jsx`
  - new `ui/src/views/V4Home.jsx`
  - new `ui/src/views/V4Home.module.css`
  - related app/home tests
- Data or API dependencies:
  - existing `/api/v4/inbox`
  - existing `/api/v4/today`
  - existing `/api/v4/entities?type=project`
- Write paths affected:
  - none expected beyond existing navigation

## Slice Intent

- Change `/` from Inbox to Home.
- Keep Inbox intact at `/inbox`.
- Home should include only:
  - Needs review
  - Today
  - Stuck
  - Active projects
  - Recent captures
- Each section must be compact and actionable, with obvious next clicks.

## Acceptance Criteria

- [ ] `/` renders Home, not Inbox.
- [ ] Home gives a compact summary of review load, today's actionable work, stuck work, active projects, and recent captures.
- [ ] Inbox remains available at `/inbox`.
- [ ] Each Home section links clearly into the next workflow or relevant entity detail.
- [ ] No new backend endpoints or schema changes are required.
- [ ] Focused frontend tests pass.
- [ ] Frontend build passes.

## Non-Goals

- [ ] No command bar yet.
- [ ] No grouped review queue yet.
- [ ] No planner/focus-state logic yet.
- [ ] No new metrics/dashboard widgets beyond immediate operational context.

## Verification Plan

- Focused tests:
  - `ui/src/App.test.jsx`
  - new `ui/src/views/V4Home.test.jsx`
- Manual QA path:
  - load `/`
  - confirm immediate orientation
  - follow links into Inbox, Today, Suggestions, and entity detail
- Broader validation if needed:
  - `cd ui && npm test`
  - `cd ui && npm run build`

## Continuity Note

- Key decisions:
  - Home must be operational, not decorative
  - use only existing v4 payloads
- Files likely to change:
  - `ui/src/App.jsx`
  - `ui/src/App.test.jsx`
  - `ui/src/views/V4Home.jsx`
  - `ui/src/views/V4Home.module.css`
  - `ui/src/views/V4Home.test.jsx`
- Main risks:
  - making Home too verbose or duplicative
  - routing changes could break expectations if Inbox is not kept visible and easy to reach
- Exact next step if interrupted:
  - finish wiring `/` to Home and ensure Inbox remains reachable at `/inbox`
