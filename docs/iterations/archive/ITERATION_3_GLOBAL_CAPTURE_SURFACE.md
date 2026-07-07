# Iteration 3 Contract

## Summary

- Iteration: 3
- Goal: add a persistent global capture/action surface so users can create or jump without leaving their current route
- Risk level: medium

## User Problem

- Capture is currently strong only on Inbox.
- Once users move into Home, Today, detail, or library views, they lose the fastest path to add a note, create a task/project, or jump to search.

## Scope

- Routes / screens / handlers affected:
  - `ui/src/App.jsx`
  - `ui/src/App.module.css`
  - app-shell tests
- Data or API dependencies:
  - existing `/api/v4/capture`
  - existing `/api/v4/entities`
  - existing `/search` route
- Write paths affected:
  - note capture
  - task creation
  - project creation

## Slice Intent

- Add a persistent app-wide quick action bar.
- Support:
  - quick note capture
  - new task
  - new project
  - jump to search
- Keep this shallow and fast. This is not a full command palette.

## Acceptance Criteria

- [ ] The quick action bar is visible from any main app route.
- [ ] Users can create a note without going back to Inbox.
- [ ] Users can create a task or project without navigating to a list first.
- [ ] Users can jump straight to Search.
- [ ] Existing routes continue to render normally beneath the action surface.
- [ ] Focused frontend tests pass.
- [ ] Frontend build passes.

## Non-Goals

- [ ] No generalized command palette taxonomy.
- [ ] No keyboard shortcut system yet.
- [ ] No person/area/resource quick create yet.
- [ ] No new backend endpoints.

## Verification Plan

- Focused tests:
  - `ui/src/App.test.jsx`
- Manual QA path:
  - trigger quick note/task/project from multiple routes
  - confirm the action succeeds and the screen remains coherent
  - jump to search from the shell
- Broader validation if needed:
  - `cd ui && npm test`
  - `cd ui && npm run build`

## Continuity Note

- Key decisions:
  - use a compact top-bar action surface
  - keep it limited to the highest-leverage actions only
- Files likely to change:
  - `ui/src/App.jsx`
  - `ui/src/App.module.css`
  - `ui/src/App.test.jsx`
- Main risks:
  - the shell can become visually noisy if the bar is too large
  - route transitions should not reset action state in confusing ways
- Exact next step if interrupted:
  - finish wiring quick note/task/project submits and verify Search navigation
