# Iteration 9 Contract

## Summary

- Iteration: 9
- Goal: turn area detail into a clearer portfolio workspace using existing relationship data
- Risk level: medium

## User Problem

- Areas are the organizing surface above projects, but area detail still reads as a generic set of relationship buckets.
- Users need to see whether an area actually has active work, where the center of gravity is, and whether basic stewardship context is missing.

## Scope

- Routes / screens / handlers affected:
  - `ui/src/views/V4EntityDetail.jsx`
  - focused tests under `ui/src/views/V4EntityScreens.test.jsx`
- Data or API dependencies:
  - existing `/api/v4/entities/:id/detail`
  - existing linked project `task_counts` on the canonical entity DTO
- Write paths affected:
  - none beyond the existing area edit, relationship, and activity update flows

## Acceptance Criteria

- [x] Area detail includes an area-only workspace overview using existing detail sections.
- [x] The workspace surfaces active projects, work rollup, coverage, and stewardship watchouts without new backend shape.
- [x] Activity updates remain directly below the main detail segment, with area workspace context beneath them.
- [x] Existing area editing and relationship flows continue to work.
- [x] Focused frontend tests pass.
- [x] Full frontend tests pass.
- [x] Frontend build passes.

## Non-Goals

- [ ] No backend schema or endpoint changes.
- [ ] No new project prioritization logic beyond simple rollup and ranking.
- [ ] No dashboarding across multiple areas.

## Verification Plan

- Focused tests:
  - `ui/src/views/V4EntityScreens.test.jsx`
- Manual QA path:
  - open an area with linked projects and confirm the lead project and rollup feel correct
  - confirm sparse areas surface reasonable stewardship warnings rather than noisy filler
  - confirm activity updates still sit above the area workspace
- Broader validation:
  - `cd ui && npm test`
  - `cd ui && npm run build`

## Continuity Note

- Key decisions:
  - treat area detail as a portfolio stewardship surface rather than only a relationship editor
  - reuse project `task_counts` already present on linked project DTOs instead of adding a backend summary endpoint
- Files likely to change:
  - `ui/src/views/V4EntityDetail.jsx`
  - `ui/src/views/V4EntityScreens.test.jsx`
  - `EXECUTION-TRACKER.md`
- Main risks:
  - over-weighting sparse project counts as if they imply real momentum
  - repeating too much of the same information already visible lower on the page
- Exact next step if interrupted:
  - finish the area workspace summary and validate the project task rollup against existing linked project DTOs
