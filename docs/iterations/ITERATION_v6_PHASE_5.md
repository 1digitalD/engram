# Iteration v6 Phase 5 — Themes + insights

Date: 2026-07-08
Status: **active**
Design: `docs/v6/SOLUTION_DESIGN.md` §5.4
Plan: `docs/v6/IMPLEMENTATION_PLAN.md` Phase 5
QC: `docs/v6/QC_LOOP.md`

## Objective

Ship theme entity type + promote, weekly digest in Review, monthly health
briefing, and People surface under `ui/src/next/`.

## Milestones

| Milestone | Tasks | Ship criteria |
|---|---|---|
| **M1 — Themes** | v6-50 + review | `theme` type; promote; retire `/convert` |
| **M2 — Weekly digest** | v6-51 + review | Cited digest in Review; UC-9 |
| **M3 — Monthly health** | v6-52 + review | `/insights/monthly`; UC-10 |
| **M4 — People UI** | v6-53 + review | Person rollup surface |
| **Gate** | v6-phase-5-gate | Full suites; review verdicts APPROVE |

Migration: `011_theme_type.sql` — test DB (:5433) first;
`bash scripts/backup_prod.sh` before prod.

## Loopsmith commands

```bash
export LOOPSMITHCTL=/Users/danish/plugins/loopsmith-orchestrator/scripts/loopsmithctl.py
bash scripts/iteration_preflight.sh /Volumes/lex1t/dev/shared/repos/engram
bash scripts/loopsmith_recover.sh /Volumes/lex1t/dev/shared/repos/engram clean-all
bash /Volumes/lex1t/dev/shared/repos/loopsmith-coding-standards/scripts/loopsmithctl-lcs.sh \
  host-run --repo /Volumes/lex1t/dev/shared/repos/engram --drain --executor codex --allow-fallback
```

## Deploy gate 5 (overseer, post-gate)

Full suites green → backup → deploy → smoke.
