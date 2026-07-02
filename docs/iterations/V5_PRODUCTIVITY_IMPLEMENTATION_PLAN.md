# V5 Productivity & Trust Loop — Implementation Plan

Date: 2026-07-02
Status: **active**
Owner: Engram
Companion spec: `docs/superpowers/plans/2026-07-02-v5-productivity-trust-loop.md`
Loopsmith overlay: `prd.json` (iteration `v5-productivity-trust-loop`)

## Working rules

Same Loopsmith slice discipline as Activity Update v2:

- smallest coherent change that proves the behavior;
- inspect current code before editing;
- preserve contracts unless the slice explicitly changes them;
- tests in the same slice as behavior changes;
- narrow validator first, then broader suites;
- Cursor overseer reviews slice output + manual smoke before marking milestone done.

## Milestones

| Milestone | Tasks | Goal |
|-----------|-------|------|
| **M1** | UI-01, UI-02, UI-03 | Trust fixes: one FAB, update outcomes visible, suggestions reviewable |
| **M2** | AU10, AU11 | Activity update closes/spins off work correctly |
| **M3** | UI-04 – UI-07 | Daily surface: Now, meeting prep, honest actions, Recall |
| **M4** | UI-08 – UI-10 | Polish: Memory, decisions, empty sections |

## Slice index

| Slice | Doc | prd task id | Risk |
|-------|-----|-------------|------|
| UI-01 | `SLICE_UI01_duplicate-fab.md` | `ui-01-duplicate-fab` | low |
| UI-02 | `SLICE_UI02_update-outcome-panel.md` | `ui-02-update-outcome-panel` | medium |
| UI-03 | `SLICE_UI03_suggestions-review.md` | `ui-03-suggestions-review` | medium |
| AU10 | `SLICE_AU10_status-extraction.md` | `au10-status-extraction` | medium |
| AU11 | `SLICE_AU11_follow-up-routing.md` | `au11-follow-up-routing` | medium |
| UI-04 | `SLICE_UI04_now-full-today.md` | `ui-04-now-full-today` | medium |
| UI-05 | `SLICE_UI05_meeting-prep.md` | `ui-05-meeting-prep` | low |
| UI-06 | `SLICE_UI06_honest-follow-up-actions.md` | `ui-06-honest-follow-up-actions` | low |
| UI-07 | `SLICE_UI07_recall-copy.md` | `ui-07-recall-copy` | low |
| UI-08 | `SLICE_UI08_memory-digest.md` | `ui-08-memory-digest` | low |
| UI-09 | `SLICE_UI09_decisions-section.md` | `ui-09-decisions-section` | low |
| UI-10 | `SLICE_UI10_collapse-empty-sections.md` | `ui-10-collapse-empty-sections` | low |

## Delivery model

- **Loopsmith drain** executes slices from `prd.json` in isolated worktrees.
- **Cursor overseer** monitors status, fixes harness drift, runs manual smoke, gates milestones.
- **LCS enabled** via `loopsmithctl-lcs.sh` wrapper (PREAMBLE + TDD skills in executor prompts).
- **Retrospective** after M1–M3 complete (Loopsmith + product learnings).

## End-to-end validation (after M1 + M2)

1. Entity detail: exactly one Capture entry point.
2. Add update with done + security review + follow up next week → outcome panel shows status + suggestion; parent not given spurious follow-up.
3. Review sheet accepts security task suggestion.
4. Manual smoke on local API.

## Continuity

Update `EXECUTION-TRACKER.md` when each slice lands. Fill **Results** in slice docs with commit SHA, test output, overseer notes.
