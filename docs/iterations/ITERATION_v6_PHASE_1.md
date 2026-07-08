# Iteration v6 Phase 1 — Distillation report + trust policy

Date: 2026-07-08
Status: **active**
Design: `docs/v6/SOLUTION_DESIGN.md` §5.1, §6, §7
Plan: `docs/v6/IMPLEMENTATION_PLAN.md` Phase 1
QC: `docs/v6/QC_LOOP.md` (implement → review → fix → APPROVE)

## Objective

Replace the loose suggestion queue with **one distillation report per capture**,
retire auto-create, and ship the `/next` Review surface. This is the load-bearing
bet for v6.

## Quality control (Phase 1)

Every implement task is followed by a **review task** that must:

1. Write `docs/v6/reviews/<implement-task-id>.md` with `Verdict: APPROVE`
2. Pass `bash scripts/v6_check_review_verdict.sh <implement-task-id>`
3. Fix product-code findings in the review worktree before approving

See `docs/v6/reviews/TEMPLATE.md`.

## Milestones

| Milestone | Tasks | Ship criteria |
|---|---|---|
| **M1 — Report pipeline** | v6-10 + review | Migration applied (test DB); assembler groups/sections; supersede-on-redistill |
| **M2 — Resolve API** | v6-11 + review | GET/POST reports; atomic ChangeBatch resolve; undo |
| **M3 — Trust policy** | v6-12 + review | Auto-create deleted; creates always propose |
| **M4 — Review UI** | v6-13 + review | `/next` shell + Review surface |
| **M5 — Metrics** | v6-14 + review | Replay eval grouping score; client review-time instrumentation |
| **Gate** | v6-phase-1-gate | Full suites; all review verdicts APPROVE; tracker updated |

Deploy gate 1 (overseer): backup + deploy + smoke after gate. Metrics tracked
in parallel — not calendar-blocking.

## Migration

`scripts/migrations/006_distillation_reports.sql` — apply to test DB (:5433)
first. Never `init-db` on prod without backup.

## Loopsmith commands

```bash
bash scripts/iteration_preflight.sh /Volumes/lex1t/dev/shared/repos/engram

bash /Volumes/lex1t/dev/shared/repos/loopsmith-coding-standards/scripts/loopsmithctl-lcs.sh \
  host-run --repo /Volumes/lex1t/dev/shared/repos/engram --drain
```

## Phase 0 prerequisite

Phase 0 retro review complete — see `docs/v6/reviews/v6-01-*.md` and
`v6-02-*.md`.
