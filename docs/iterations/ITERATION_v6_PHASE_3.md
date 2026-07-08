# Iteration v6 Phase 3 — Dossier + direct manipulation + pinning

Date: 2026-07-08
Status: **archived** (2026-07-08)
Design: `docs/v6/SOLUTION_DESIGN.md` §5.2, §5.5, §7.3–7.4
Plan: `docs/v6/IMPLEMENTATION_PLAN.md` Phase 3
QC: `docs/v6/QC_LOOP.md`

## Objective

Ship pin enforcement (human edits pin; AI demotes on pinned fields), typed
inline affordances, amend/archive/redact/delete lifecycle verbs, and the Space
Dossier surface under `ui/src/next/`.

## Milestones

| Milestone | Tasks | Ship criteria |
|---|---|---|
| **M1 — Pin enforcement** | v6-30 + review | `pinned_fields` column; `v4_trust.check_pin`; pin/unpin endpoints; TC-30..32 |
| **M2 — Typed affordances** | v6-31 + review | Inline chips, move-to-Space, fast paths; all write Ledger events |
| **M3 — Lifecycle verbs** | v6-32 + review | Amend, archive, delete tombstone, note redaction; TC-34..36 |
| **M4 — Dossier UI** | v6-33 + review | Brief + Spine + commitments + Ledger tab |
| **Gate** | v6-phase-3-gate | Full suites; review verdicts APPROVE |

Migrations: `008_pinned_fields.sql`, `009_redacted_lifecycle.sql` — test DB
(:5433) first; `bash scripts/backup_prod.sh` before prod.

## Loopsmith commands

```bash
bash scripts/iteration_preflight.sh /Volumes/lex1t/dev/shared/repos/engram
bash scripts/loopsmith_recover.sh /Volumes/lex1t/dev/shared/repos/engram clean-all
bash /Volumes/lex1t/dev/shared/repos/loopsmith-coding-standards/scripts/loopsmithctl-lcs.sh \
  host-run --repo /Volumes/lex1t/dev/shared/repos/engram --drain --executor codex --allow-fallback
```

## Deploy gate 3 (overseer, post-gate)

Full suites green → backup → deploy → smoke. Verify pin behavior: paste a
transcript contradicting a pinned date → must propose, not overwrite.
