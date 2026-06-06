# Iteration 5 Contract

## Summary

- Iteration: 5
- Goal: strengthen project detail into a clearer workspace for status, momentum, and obvious gaps
- Risk level: medium

## User Problem

- Projects already contain the right linked data, but the page still reads like a generic relationship editor.
- Users need a fast read on whether a project has momentum, what the next step is, and what is missing.

## Scope

- Routes / screens / handlers affected:
  - `ui/src/views/V4EntityDetail.jsx`
  - `ui/src/views/V4EntityScreens.module.css`
  - `ui/src/views/V4EntityScreens.test.jsx`
- Data or API dependencies:
  - existing `/api/v4/entities/:id/detail`
  - existing activity updates endpoint remains unchanged
- Write paths affected:
  - none beyond the existing entity/relationship/activity update flows already on the page

## Slice Intent

- Add a project-only workspace overview above the relationship segments.
- Surface open/completed task counts, people, notes, and resources at a glance.
- Highlight the next actionable task when available.
- Flag obvious hygiene gaps such as no open tasks, no area, no review date, or no linked notes.

## Acceptance Criteria

- [x] Project detail includes a project-only overview panel using existing detail sections.
- [x] The panel surfaces momentum counts and a next-step link without new backend data.
- [x] The panel highlights clear project hygiene gaps when the project lacks basic steering artifacts.
- [x] Existing project relationship flows continue to work.
- [x] Focused frontend tests pass.
- [x] Full frontend tests pass.
- [x] Frontend build passes.

## Non-Goals

- [ ] No new project-specific endpoint.
- [ ] No persisted project health model.
- [ ] No full timeline/events redesign in this slice.
- [ ] No custom planner state tied to projects.

## Verification Plan

- Focused tests:
  - `ui/src/views/V4EntityScreens.test.jsx`
- Manual QA path:
  - open a populated project
  - verify workspace counts, next step, and watchouts
  - confirm relationship sections still behave normally
- Broader validation:
  - `cd ui && npm test`
  - `cd ui && npm run build`

## Continuity Note

- Key decisions:
  - reuse existing detail sections rather than add backend shape
  - keep the project workspace additive and project-only
- Files changed:
  - `ui/src/views/V4EntityDetail.jsx`
  - `ui/src/views/V4EntityScreens.module.css`
  - `ui/src/views/V4EntityScreens.test.jsx`
- Main risks:
  - duplicate visibility between overview and existing relationship sections
  - too many warnings if project metadata is sparse
- Exact next step if interrupted:
  - run a live visual QA pass on a populated project detail, then decide whether to continue to inspection/trust surfaces or tighten the project slice further
