# Iteration 0 Contract

## Summary

- Iteration: 0
- Goal: remove interaction ambiguity from the current v4 UI baseline before adding new product surfaces
- Risk level: medium

## User Problem

- The current UI makes some important actions feel unreliable or internally inconsistent.
- Users cannot always tell when edits are already saved, when they are still drafts, or whether counts and queues reflect the actual underlying state.
- If this is not fixed first, later control-plane/planner improvements will sit on top of weak trust semantics.

## Scope

- Routes / screens / handlers affected:
  - `ui/src/App.jsx`
  - `ui/src/views/V4EntityDetail.jsx`
  - `ui/src/views/V4Today.jsx`
  - related tests under `ui/src/views/*test.jsx`
- Data or API dependencies:
  - existing `/api/v4/today`
  - existing `/api/v4/entities/:id`
  - no schema changes expected
- Write paths affected:
  - entity detail editing
  - task status/date quick updates in Today

## Slice Intent

- Pick one clear persistence model for the entity detail experience.
- Align sidebar counts with the same payload concepts used by the destination views.
- Standardize obvious loading/error/empty-state behavior where it directly affects trust in the touched surfaces.
- Do not redesign workflows yet. This slice is about interaction integrity, not new product structure.

## Acceptance Criteria

- [ ] Entity detail follows one consistent save model that a user can predict without guessing.
- [ ] The detail screen no longer mixes immediate-save field writes with a competing page-level Save affordance.
- [ ] Sidebar `Today` count reflects the actual `Today` screen's actionable buckets.
- [ ] Touched screens keep explicit, visible feedback for loading and save/error states.
- [ ] Existing create/capture behavior on Inbox and list pages remains intact.
- [ ] Frontend tests are updated to reflect the new interaction model and pass.
- [ ] Frontend build passes.

## Non-Goals

- [ ] No new Home/control-plane route yet.
- [ ] No grouped review queue yet.
- [ ] No command bar / global capture surface yet.
- [ ] No backend schema changes.
- [ ] No broad visual redesign.

## Verification Plan

- Focused tests:
  - `ui/src/views/V4EntityScreens.test.jsx`
  - `ui/src/views/V4Today.test.jsx`
  - any touched route tests needed for regressions
- Manual QA path:
  - open entity detail
  - edit title/content/status/priority/date
  - confirm save behavior is obvious and consistent
  - load Today and compare sidebar badge with visible actionable items
- Broader validation if needed:
  - `cd ui && npm test`
  - `cd ui && npm run build`

## Continuity Note

- Key decisions:
  - interaction consistency outranks adding new surfaces in this slice
  - fix trust semantics before building Home or planner features
- Files likely to change:
  - `ui/src/App.jsx`
  - `ui/src/views/V4EntityDetail.jsx`
  - `ui/src/views/V4Today.jsx`
  - `ui/src/views/V4EntityScreens.test.jsx`
  - `ui/src/views/V4Today.test.jsx`
- Main risks:
  - changing save semantics may require test rewrites and small UX copy/feedback adjustments
  - quick-update behavior in Today must remain fast while not reintroducing ambiguity
- Exact next step if interrupted:
  - inspect current detail save paths and choose the concrete consistency model to implement first
