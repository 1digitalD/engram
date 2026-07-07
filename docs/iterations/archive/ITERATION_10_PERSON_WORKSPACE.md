# Iteration 10 Contract

## Summary

- Iteration: 10
- Goal: turn person detail into a clearer coordination workspace using existing relationship data
- Risk level: medium

## User Problem

- People are a real coordination surface in v4, but person detail still reads as a generic relationship stack.
- Users need a fast view of assigned work, active projects, supporting notes, and whether a person has gone stale as an execution surface.

## Scope

- Routes / screens / handlers affected:
  - `ui/src/views/V4EntityDetail.jsx`
  - focused tests under `ui/src/views/V4EntityScreens.test.jsx`
- Data or API dependencies:
  - existing `/api/v4/entities/:id/detail`
- Write paths affected:
  - none beyond the existing person edit, relationship, and activity update flows

## Acceptance Criteria

- [x] Person detail includes a person-only workspace overview using existing detail sections.
- [x] The workspace surfaces current load, coverage, and coordination watchouts without new backend shape.
- [x] Existing person editing and relationship flows continue to work.
- [x] Focused frontend tests pass.
- [x] Full frontend tests pass.
- [x] Frontend build passes.

## Non-Goals

- [ ] No backend schema or endpoint changes.
- [ ] No new people-assignment workflow beyond existing relationship editing.
- [ ] No attempt to infer ownership beyond existing assigned task and project links.

## Verification Plan

- Focused tests:
  - `ui/src/views/V4EntityScreens.test.jsx`
- Manual QA path:
  - open a person with assigned tasks and confirm the load summary feels useful
  - confirm sparse people show watchouts instead of empty filler
  - confirm person relationship sections still behave normally below the workspace panel
- Broader validation:
  - `cd ui && npm test`
  - `cd ui && npm run build`

## Continuity Note

- Key decisions:
  - treat person detail as a coordination surface rather than only a relationship editor
  - reuse existing assigned task, project, note, and resource sections instead of adding summary API shape
- Files likely to change:
  - `ui/src/views/V4EntityDetail.jsx`
  - `ui/src/views/V4EntityScreens.test.jsx`
  - `EXECUTION-TRACKER.md`
- Main risks:
  - overstating “ownership” from sparse or weak links
  - repeating too much of the same relationship data lower on the page
- Exact next step if interrupted:
  - finish the person workspace summary and validate it against real assigned-task-heavy people
