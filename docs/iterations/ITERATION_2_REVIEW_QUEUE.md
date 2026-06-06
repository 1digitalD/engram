# Iteration 2 Contract

## Summary

- Iteration: 2
- Goal: turn suggestion review into a source-note-centered queue instead of a flat list
- Risk level: medium

## User Problem

- Suggestions currently appear as isolated cards with too little source context.
- Review work is cognitively fragmented: users can see a suggestion, but not enough of the note it came from, the grouping of related suggestions, or a fast path to clear a note from review.

## Scope

- Routes / screens / handlers affected:
  - `ui/src/views/V4Suggestions.jsx`
  - `ui/src/views/V4Suggestions.module.css`
  - related suggestions tests
- Data or API dependencies:
  - existing `/api/v4/suggestions`
  - existing `/api/v4/entities/:id`
- Write paths affected:
  - accept suggestion
  - dismiss suggestion
  - optional suggestion update for editable create actions

## Slice Intent

- Group pending suggestions by source note when `source_entity_id` is present.
- Show compact source-note context inside each group.
- Support per-suggestion actions and per-note batch clear actions.
- Keep risky changes reviewable and explicit.

## Acceptance Criteria

- [ ] Suggestions are grouped by source note when possible.
- [ ] Each group shows clear source context and the related suggestions beneath it.
- [ ] Per-suggestion accept/dismiss still works.
- [ ] Per-group accept-all / dismiss-all works.
- [ ] Ungrouped suggestions still render safely.
- [ ] Focused frontend tests pass.
- [ ] Frontend build passes.

## Non-Goals

- [ ] No backend endpoint changes.
- [ ] No full Inbox redesign yet.
- [ ] No new AI/agent behaviors.
- [ ] No planner changes.

## Verification Plan

- Focused tests:
  - `ui/src/views/V4Suggestions.test.jsx`
- Manual QA path:
  - open Suggestions
  - review grouped note context
  - accept/dismiss single items and full groups
- Broader validation if needed:
  - `cd ui && npm test`
  - `cd ui && npm run build`

## Continuity Note

- Key decisions:
  - keep review centered on source notes
  - use existing entity fetches for context instead of changing the backend
- Files likely to change:
  - `ui/src/views/V4Suggestions.jsx`
  - `ui/src/views/V4Suggestions.module.css`
  - `ui/src/views/V4Suggestions.test.jsx`
- Main risks:
  - sequential group actions must keep UI state consistent
  - some suggestions may not have `source_entity_id` and need a safe fallback group
- Exact next step if interrupted:
  - finish grouping logic and preserve existing single-suggestion actions
