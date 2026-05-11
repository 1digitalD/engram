# Engram v2 — Execution Tracker

Last updated: 2026-05-11
Branch: `claude/busy-wozniak-e23763` → target: `main`
Architecture: Postgres + pgvector (replaces SQLite + sqlite-vec)

## Operating principles

- Write tests first. Confirm failure. Implement. Confirm passing. Report.
- A task is done only when its tests pass and the full suite still passes.
- Commit logical, reviewable units — one commit per task or meaningful sub-step.
- Update this file after each completed or blocked task.
- Do not touch `.venv/` — leave it alone, do not commit it.

## Active docs (read before starting any task)

| Document | Purpose |
|---|---|
| `docs/PRD.md` | Product vision, entity model, lifecycle, cycle goals |
| `docs/TECH_SPEC.md` | Stack, architecture, service contracts, migration mapping |
| `docs/SCHEMA.sql` | Canonical Postgres schema — source of truth |
| `docs/API_SPEC.md` | All routes, request/response shapes, backward-compat rules |
| `docs/TEST_STRATEGY.md` | TDD approach, conftest fixtures, test patterns |
| `docs/AGENT_PLAN.md` | Task breakdown, file ownership map, done criteria |

## Task log

| Task | Agent | Status | Commit | Tests | Notes |
|---|---|---|---|---|---|
| Setup: AGENTS.md, .env.example, requirements.txt | manual | done | 5977f5d | — | v2 pivot commit |
| C1-INFRA | manual | done | 0d98347 | schema apply + migration smoke | Added isolated test compose, hardened schema apply, fixed immutable generated column, added SQLite→Postgres migration with row-count validation. |

## Cycle 1 — Foundation

> Sequential: C1-INFRA must complete before the parallel block.

| Task | Description | Status | Blocked by |
|---|---|---|---|
| C1-INFRA | Docker + schema + migration script | done | — |
| C1-MODELS | SQLAlchemy models rewrite | pending | — |
| C1-SERVICES-CORE | entity_service + link_service | pending | C1-MODELS |
| C1-JOBS | Job worker + retry | pending | C1-MODELS |
| C1-AI-PIPELINE | Unified async AI pipeline | pending | C1-MODELS, C1-JOBS |
| C1-API | Update all API routes | pending | C1-MODELS, C1-SERVICES-CORE, C1-AI-PIPELINE |
| C1-SEARCH | Postgres FTS + pgvector search | pending | C1-MODELS |
| C1-VALIDATE | Full suite + migration validation | pending | all C1 parallel tasks |

## Cycle 2 — Relationships + UX

| Task | Description | Status | Blocked by |
|---|---|---|---|
| C2-LINKS-API | Universal entity links API | pending | C1-VALIDATE |
| C2-EDITOR | TipTap note editor | pending | C1-VALIDATE |
| C2-KANBAN | Task kanban board | pending | C1-VALIDATE |
| C2-SURFACING | Proactive related entities | pending | C1-VALIDATE |
| C2-VALIDATE | Full suite + build | pending | all C2 tasks |

## Cycle 3 — AI Reliability

| Task | Description | Status | Blocked by |
|---|---|---|---|
| C3-SELECTION | Text selection → AI proposal | pending | C2-VALIDATE |
| C3-SEARCH-UNIVERSAL | Universal search (all entity types) | pending | C2-VALIDATE |
| C3-AI-QUALITY | Confidence calibration + correction signals | pending | C2-VALIDATE |
| C3-VALIDATE | Full suite + coverage gates | pending | all C3 tasks |

## Recovery notes

If the session resets:
1. Re-read this file and `docs/AGENT_PLAN.md`.
2. Run `git log --oneline -10` to find the latest commit.
3. Run `git status` to check for uncommitted work.
4. Resume the first `pending` task in the table above.
5. Re-run the relevant validation command before continuing.

- **2026-05-11 12:14** C1-MODELS → 1501a0e: C1-MODELS: completed, merged from opencode worktree

- **2026-05-11 14:10** C1-AI-PIPELINE → 723e184: C1-AI-PIPELINE: completed, merged from opencode worktree
