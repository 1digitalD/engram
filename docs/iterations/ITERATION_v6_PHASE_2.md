# Iteration v6 Phase 2 — Workboard

Date: 2026-07-08
Status: **archived** (2026-07-08)
Design: `docs/v6/SOLUTION_DESIGN.md` §10.1
Plan: `docs/v6/IMPLEMENTATION_PLAN.md` Phase 2
QC: `docs/v6/QC_LOOP.md`

## Objective

Ship derived workboard states + `GET /workboard` and the Workboard + Stream
surfaces under `ui/src/next/`.

## Milestones

| Milestone | Tasks | Ship criteria |
|---|---|---|
| **M1 — Backend** | v6-20 + review | `GET /workboard` with states, grouping, at-risk v1 + hysteresis |
| **M2 — Workboard UI** | v6-21 + review | Filter chips, group toggle, inline actions (placeholders OK) |
| **M3 — Stream UI** | v6-22 + review | Chronological capture log |
| **Gate** | v6-phase-2-gate | Full suites; review verdicts APPROVE |

No migrations in Phase 2 (query-time derived states).

## Loopsmith commands

```bash
bash scripts/iteration_preflight.sh /Volumes/lex1t/dev/shared/repos/engram
bash /Volumes/lex1t/dev/shared/repos/loopsmith-coding-standards/scripts/loopsmithctl-lcs.sh \
  host-run --repo /Volumes/lex1t/dev/shared/repos/engram --drain --executor codex --allow-fallback
```
