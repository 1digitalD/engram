# Iteration 18 — V5 Productivity & Trust Loop

## Summary

- Iteration: `v5-productivity-trust-loop`
- Goal: close the gap between backend intelligence and daily-use UI; restore the capture → extract → review → act loop
- Risk level: medium
- Delivery: Loopsmith drain + LCS + Cursor overseer (retrospective after M1–M3)

## User Problem

- Add update saves prose but entity metadata appears unchanged; status/spin-off work not handled on the Add update path.
- Capture FAB renders twice on entity detail pages.
- No V5 suggestions review surface despite API and capture toast counts.
- Now underuses `/api/v4/today`; meeting prep invisible; Recall/Snooze copy over-promises.

## Scope

- Routes / screens: entity detail, Now, Recall, review sheet, activity update POST
- Backend: `extract_dates_and_tasks_from_update`, `create_activity_update`
- Write paths: status/follow-up policy, suggestion review UI

## Acceptance Criteria (milestones)

- [ ] **M1:** One FAB; update outcomes visible; suggestions reviewable
- [ ] **M2:** Done + spin-off task + follow-up scenario covered by tests
- [ ] **M3:** Now complete; meeting prep; honest actions; Recall copy
- [ ] **M4:** Memory/decisions/empty sections (optional polish)

## Non-Goals

- Phase 4 multimodal capture
- Full relationship editing on detail pages
- Re-enabling capture progress_update on thread-attached capture

## Verification Plan

- Per-slice `validationCommands` in `prd.json`
- Manual smoke after M2 (see `V5_PRODUCTIVITY_IMPLEMENTATION_PLAN.md`)
- Retrospective on Loopsmith harness + product outcomes when iteration drains

## Continuity Note

- Plan: `docs/iterations/V5_PRODUCTIVITY_IMPLEMENTATION_PLAN.md`
- Archived prd: `docs/iterations/archive/prd-v5-hardening.json`
- Overseer: monitor `loopsmithctl status`, fix harness drift, gate milestones
- Next step if interrupted: `loopsmithctl status --repo .../engram` then resume drain or `--task-id`
