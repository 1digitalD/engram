# Iteration 8 Contract

## Summary

- Iteration: 8
- Goal: turn task detail into a clearer execution workspace without changing backend shape
- Risk level: medium

## User Problem

- Tasks are the main unit of execution, but task detail still reads mostly like a generic relationship editor.
- Users need fast clarity on task context: what project it belongs to, who owns it, what source note or references support it, and whether blockers or missing review dates make it risky.

## Scope

- Routes / screens / handlers affected:
  - `ui/src/views/V4EntityDetail.jsx`
  - focused tests under `ui/src/views/V4EntityScreens.test.jsx`
- Data or API dependencies:
  - existing `/api/v4/entities/:id/detail`
  - existing `/api/v4/entities/:id/activity_updates`
- Write paths affected:
  - none beyond the existing task edit, relationship, and activity update flows

## Acceptance Criteria

- [x] Task detail includes a task-only workspace overview using existing detail sections.
- [x] The workspace surfaces ownership, scope, supporting context, and execution watchouts without new backend shape.
- [x] Activity updates remain directly below the main detail segment, with the task workspace below them.
- [x] Existing task editing and relationship flows continue to work.
- [x] Focused frontend tests pass.
- [x] Full frontend tests pass.
- [x] Frontend build passes.

## Non-Goals

- [ ] No backend schema or endpoint changes.
- [ ] No new task status workflow beyond existing edit controls.
- [ ] No embedded suggestion review inside task detail.

## Verification Plan

- Focused tests:
  - `ui/src/views/V4EntityScreens.test.jsx`
- Manual QA path:
  - open a task with project, source note, and blockers linked
  - confirm activity updates still sit above the workspace panel
  - confirm the workspace watchouts read correctly for waiting/blocked tasks
- Broader validation:
  - `cd ui && npm test`
  - `cd ui && npm run build`

## Continuity Note

- Key decisions:
  - treat task detail as an execution surface, not only a relationship bucket stack
  - reuse existing task detail sections rather than adding backend summary fields
- Files likely to change:
  - `ui/src/views/V4EntityDetail.jsx`
  - `ui/src/views/V4EntityScreens.test.jsx`
  - `EXECUTION-TRACKER.md`
- Main risks:
  - over-signaling normal sparse tasks as if they are broken
  - duplicating too much of what the relationship sections already show
- Exact next step if interrupted:
  - finish task workspace rendering and validate it against waiting/blocked task states
