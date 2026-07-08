# Iteration v6 Phase 4 — Today + markers + nudges

Date: 2026-07-08
Status: **active**
Design: `docs/v6/SOLUTION_DESIGN.md` §5.3
Plan: `docs/v6/IMPLEMENTATION_PLAN.md` Phase 4
QC: `docs/v6/QC_LOOP.md`

## Objective

Ship follow-up markers (CRUD + firing job), the Today surface under
`ui/src/next/`, nudge draft endpoint + copy UX, and meeting prep integration.

## Milestones

| Milestone | Tasks | Ship criteria |
|---|---|---|
| **M1 — Markers backend** | v6-40 + review | `followup_markers` table; CRUD; firing job; TC-40..42 |
| **M2 — Today UI** | v6-41 + review | Needs-you / in-motion split; fired markers; UC-6 |
| **M3 — Nudge drafting** | v6-42 + review | `POST /nudge-draft`; copy UX; TC-44 |
| **M4 — Meeting prep** | v6-43 + review | Prep payload with discuss markers; UC-8 |
| **Gate** | v6-phase-4-gate | Full suites; review verdicts APPROVE |

Migration: `010_followup_markers.sql` — test DB (:5433) first;
`bash scripts/backup_prod.sh` before prod.

## Loopsmith commands

```bash
export LOOPSMITHCTL=/Users/danish/plugins/loopsmith-orchestrator/scripts/loopsmithctl.py
bash scripts/iteration_preflight.sh /Volumes/lex1t/dev/shared/repos/engram
bash scripts/loopsmith_recover.sh /Volumes/lex1t/dev/shared/repos/engram clean-all
bash /Volumes/lex1t/dev/shared/repos/loopsmith-coding-standards/scripts/loopsmithctl-lcs.sh \
  host-run --repo /Volumes/lex1t/dev/shared/repos/engram --drain --executor codex --allow-fallback
```

## Deploy gate 4 (overseer, post-gate)

Full suites green → backup → deploy → smoke.
