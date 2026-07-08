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

## Loopsmith friction log (Phase 1 drain)

Captured for Loopsmith reinforcement — each entry: symptom → root cause →
workaround → proposed harness fix. Raw evidence lives in `.codloop/runs/*.json`
(archived under `.codloop/runs/.archive-*`).

| Date | Task | Failure class | Symptom | Root cause | Workaround | Proposed Loopsmith fix |
|---|---|---|---|---|---|---|
| 2026-07-08 | v6-13-code-review | `merge_conflict` | Cursor attempts a062/a063 blocked | Review-only task; UI already green on `main`; executor tried to merge/publish with nothing to land | Overseer takeover: write verdict file, mark `passes: true`, `clean-all`, resume | Classify review tasks with zero product delta as **verdict-only**; skip integrate-before-validate when implement task already on `main` |
| 2026-07-08 | v6-13-code-review | `tool_unavailable` | OpenCode attempt a061 | OpenCode credits exhausted | Fallback to Cursor (also failed) → overseer | Surface credits error earlier; auto-fallback without stale-blocker exit |
| 2026-07-08 | v6-14-eval-metrics | `validation_failure` | Codex a064 blocked | (1) test asserted `corrections.total == 3` but formula yields 4; (2) `replay_eval.py` not executable | Overseer cherry-pick worktree + fix assertions + `chmod +x` | Post-impl lint: flag executable scripts referenced by unit tests; validation summary should highlight **assertion mismatch** vs code bug |
| 2026-07-08 | (harness) | policy | First drain blocked | `validationTimeoutSeconds` in `coding-loop-policy.yaml` stripped by `doctor` | Move timeout to `prd.json` → `codingLoopPolicy` | Document protected keys; `doctor` should warn not silently strip |
| 2026-07-08 | (harness) | stale state | Resume exits in ~10s | Prior `blocked` attempt still in `.codloop/state.json` | `loopsmith_recover.sh clean-all` before retry | `host-run --drain` should auto-clear stale blocker when `passes: true` already set on blocked task |
| 2026-07-08 | Phase 0 reviews | QC gap | Review tasks `passes: true` without verdict files | Validation = pytest only, no verdict gate | Phase 1 retro + `v6_check_review_verdict.sh` | Review tasks must include verdict script in `validationCommands` (now in prd template) |

**Feedback targets:** `loopsmith/docs/proving-runs.md` (orchestration evidence),
`loopsmith/docs/failure-model.md` (recovery rules), overseer skill common-blockers
table. Engram-side backlog: `docs/v6/QC_LOOP.md` §Loopsmith harness backlog.
