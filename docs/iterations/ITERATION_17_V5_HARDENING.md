# Iteration 17 - V5 Hardening

## Summary

- Iteration: `v5-postphase3-hardening`
- Goal: close the remaining trust, routing, and reliability gaps in the v5 redesign with thin slices that can run cleanly through Loopsmith drain mode
- Risk level: medium

## User Problem

- Phase 3 shipped the main v5 surfaces, but a few gaps still separate "tests pass" from "the app behaves like a trustworthy workspace."
- The highest-risk issues are honesty in Ask, truthfulness in top-bar counts, Recall stability, semantic correctness of `New`, and the reliability of backend validation itself.

## Scope

- Routes / screens / handlers affected:
  - `POST /api/v4/ask`
  - `GET /api/v4/summary`
  - `GET /api/v4/threads`
  - `/recall`
  - entity list screens and capture flows
- Data or API dependencies:
  - test DB isolation must remain safe and bounded
  - summary counts must be derived from real data or omitted
  - Recall route behavior must stay stable across refresh and direct load
- Write paths affected:
  - Ask response envelope
  - summary payload shape
  - possible creation-flow payloads
  - test reset path

## Acceptance Criteria

- [ ] Each hardening slice is independently runnable through Loopsmith.
- [ ] Trust-sensitive bugs are fixed before UX polish.
- [ ] Loop-level learnings are captured in `EXECUTION-TRACKER.md` rather than left implicit.

## Non-Goals

- [ ] Reopening broad Phase 3 product scope
- [ ] Large new features unrelated to the known hardening list
- [ ] Replacing Loopsmith with a manual delivery loop

## Verification Plan

- Focused tests:
  - backend ask/integration tests
  - frontend tests for Ask, Recall, capture, and entity-list flows
  - bounded `loopsmithctl doctor --strict` probe
- Manual QA path:
  - Ask honest-IDK path
  - Recall direct load and search ordering
  - entity-list `New` flow
- Broader validation if needed:
  - frontend build
  - targeted live API curl checks

## Continuity Note

- Key decisions:
  - treat `prd.json` as a temporary Loopsmith execution overlay for this hardening loop, even though the repo's longer-term planning source of truth lives elsewhere
  - keep slices thin and ordered by trust/reliability first
- Files likely to change:
  - `prd.json`
  - `EXECUTION-TRACKER.md`
  - `tests/conftest.py`
  - `services/v4_ask.py`
  - `api/v4_entities.py`
  - `ui/src/App.jsx`
  - `ui/src/views/V5AskSheet.jsx`
  - `ui/src/views/V5Recall*.jsx`
  - `ui/src/views/V5EntityList.jsx`
- Main risks:
  - backend validation remains flaky and undermines the rest of the loop
  - Loopsmith doctor still hangs and obscures readiness state
  - `New` semantics may need a product-level decision encoded in code, not just copy
- Exact next step if interrupted:
  - run `python3 /Users/danish/.openclaw/agents/main/agent/codex-home/skills/loopsmith-coding/scripts/loopsmithctl.py status --repo /Volumes/lex1t/dev/shared/repos/engram`
  - if the new task graph is visible, launch drain and monitor the first slice
