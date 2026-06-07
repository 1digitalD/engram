# Iteration 11 Contract

## Summary

- Iteration: 11
- Goal: turn resource detail into a clearer adoption workspace using existing relationship data
- Risk level: medium

## User Problem

- Resources are reference artifacts that should show where they are actually in use, but resource detail still reads as a generic relationship stack.
- Users need to quickly see the main anchor context for a resource, where it is linked, and whether it is drifting without active usage.

## Scope

- Routes / screens / handlers affected:
  - `ui/src/views/V4EntityDetail.jsx`
  - focused tests under `ui/src/views/V4EntityScreens.test.jsx`
- Data or API dependencies:
  - existing `/api/v4/entities/:id/detail`
- Write paths affected:
  - none beyond the existing resource edit and relationship flows

## Acceptance Criteria

- [x] Resource detail includes a resource-only workspace overview using existing detail sections.
- [x] The workspace surfaces primary anchor context, coverage, and adoption watchouts without new backend shape.
- [x] Existing resource editing and relationship flows continue to work.
- [x] Focused frontend tests pass.
- [x] Full frontend tests pass.
- [x] Frontend build passes.

## Non-Goals

- [ ] No backend schema or endpoint changes.
- [ ] No new resource recommendation logic beyond simple linked-context prioritization.
- [ ] No attempt to infer a single canonical owner for resources.

## Verification Plan

- Focused tests:
  - `ui/src/views/V4EntityScreens.test.jsx`
- Manual QA path:
  - open a resource linked to active project/task work and confirm the primary anchor feels correct
  - confirm sparse resources show adoption watchouts rather than empty filler
  - confirm resource relationship sections still behave normally below the workspace panel
- Broader validation:
  - `cd ui && npm test`
  - `cd ui && npm run build`

## Continuity Note

- Key decisions:
  - treat resource detail as an adoption surface rather than only a relationship editor
  - reuse existing linked note, project, task, area, person, and related-resource sections instead of adding summary API shape
- Files likely to change:
  - `ui/src/views/V4EntityDetail.jsx`
  - `ui/src/views/V4EntityScreens.test.jsx`
  - `EXECUTION-TRACKER.md`
- Main risks:
  - choosing an unhelpful primary anchor when multiple links exist
  - repeating too much of the same relationship data lower on the page
- Exact next step if interrupted:
  - finish the resource workspace summary and validate it against real linked project/resource data
