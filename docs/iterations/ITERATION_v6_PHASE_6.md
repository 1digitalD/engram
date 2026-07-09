# Iteration v6 Phase 6 — Cutover + MCP

Date: 2026-07-08
Status: **active**
Design: `docs/v6/SOLUTION_DESIGN.md` §9
Plan: `docs/v6/IMPLEMENTATION_PLAN.md` Phase 6
QC: `docs/v6/QC_LOOP.md`

## Objective

Promote v6 shell to `/`, preserve V5 at `/legacy/*`, align MCP tools, finalize
docs. **V6-61 legacy deletion is deferred** — rollback tag `engram/v6-phase-5-complete`.

## Milestones

| Milestone | Tasks | Ship criteria |
|---|---|---|
| **M1 — Cutover** | v6-60 + review | `/` = NextApp; `/legacy/*` = V5 |
| **M2 — MCP** | v6-62 + review | Report/workboard/marker/nudge tools |
| **M3 — Docs** | v6-63 + review | README/AGENTS/tracker updated |
| **Gate** | v6-phase-6-gate | Full suites; review verdicts APPROVE |

## Loopsmith commands

```bash
export LOOPSMITHCTL=/Users/danish/plugins/loopsmith-orchestrator/scripts/loopsmithctl.py
bash scripts/iteration_preflight.sh /Volumes/lex1t/dev/shared/repos/engram
bash scripts/loopsmith_recover.sh /Volumes/lex1t/dev/shared/repos/engram clean-all
bash /Volumes/lex1t/dev/shared/repos/loopsmith-coding-standards/scripts/loopsmithctl-lcs.sh \
  host-run --repo /Volumes/lex1t/dev/shared/repos/engram --drain --executor codex --allow-fallback
```

## Deploy gate 6 (overseer, post-gate)

Full suites → `bash scripts/backup_prod.sh` → deploy → smoke → record §5 metrics.
