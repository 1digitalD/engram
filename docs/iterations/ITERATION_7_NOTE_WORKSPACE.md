# Iteration 7 Contract

## Summary

- Iteration: 7
- Goal: turn note detail into a clearer source-artifact workspace for extraction outcomes and pending review
- Risk level: medium

## User Problem

- Notes are the primary capture artifact in v4, but note detail still reads mostly like a generic editor plus relationship buckets.
- After capture, users need a fast read on what the note produced, whether review is still pending, and where to go next without manually scanning every relationship section.

## Scope

- Routes / screens / handlers affected:
  - `ui/src/views/V4EntityDetail.jsx`
  - `ui/src/views/V4EntityScreens.module.css`
  - focused tests under `ui/src/views/V4EntityScreens.test.jsx`
- Data or API dependencies:
  - existing `/api/v4/entities/:id/detail`
  - existing `/api/v4/suggestions`
- Write paths affected:
  - none beyond the existing note edit, reprocess, and suggestion flows

## Acceptance Criteria

- [x] Note detail includes a note-only workspace overview using existing detail sections and suggestion data.
- [x] The workspace surfaces extraction outcome counts and pending review state without new backend shape.
- [x] When the note still has pending suggestions, the page gives a direct path back to review.
- [x] Existing note editing and relationship flows continue to work.
- [x] Focused frontend tests pass.
- [x] Full frontend tests pass.
- [x] Frontend build passes.

## Non-Goals

- [ ] No backend schema or endpoint changes.
- [ ] No new suggestion accept/dismiss workflow inside note detail.
- [ ] No attempt to infer that every note should always create entities.

## Verification Plan

- Focused tests:
  - `ui/src/views/V4EntityScreens.test.jsx`
- Manual QA path:
  - open a note with linked entities and confirm extraction outcome counts
  - open a note with pending suggestions and verify the review callout
  - confirm note relationship sections still behave normally
- Broader validation:
  - `cd ui && npm test`
  - `cd ui && npm run build`

## Continuity Note

- Key decisions:
  - treat note detail as a source-artifact workspace rather than only a generic relationship editor
  - reuse existing detail sections and the pending suggestions list instead of adding API shape
- Files likely to change:
  - `ui/src/views/V4EntityDetail.jsx`
  - `ui/src/views/V4EntityScreens.module.css`
  - `ui/src/views/V4EntityScreens.test.jsx`
  - `EXECUTION-TRACKER.md`
- Main risks:
  - over-signaling sparse notes as if they are incomplete
  - duplicating too much information already visible in relationship sections
- Exact next step if interrupted:
  - finish the note workspace panel and wire pending-suggestion counting from the existing suggestions endpoint
