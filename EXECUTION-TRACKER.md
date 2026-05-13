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
| C1-VALIDATE | Full suite + migration validation | done | all C1 parallel tasks |

- **2026-05-11 19:05** C1-VALIDATE → <pending>: Full suite passes — 281 passed, 2 skipped, 0 failures

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

- **2026-05-11 14:59** C1-API → bfc09a8: C1-API: completed, merged from opencode worktree

- **2026-05-11 15:24** C1-SEARCH → 4a1714d: C1-SEARCH: completed, merged from opencode worktree

- **2026-05-11 19:10** C1-VALIDATE → <pending>: Full suite passes — 281 passed, 2 skipped, 0 failures. All C1 tasks validated together with no regressions.

- **2026-05-11 15:46** C1-VALIDATE → 9a1b9f6: C1-VALIDATE: completed, merged from opencode worktree

- **2026-05-11 16:16** C2-LINKS-API → e54a779: C2-LINKS-API: completed, merged from opencode worktree

- **2026-05-11 16:40** C2-EDITOR → ce5f5e3: C2-EDITOR: completed, merged from opencode worktree

- **2026-05-11 16:46** C2-KANBAN → 7e8f664: C2-KANBAN: completed, merged from opencode worktree

- **2026-05-11 16:56** C2-SURFACING → 077a885: C2-SURFACING: completed, merged from opencode worktree

- **2026-05-11 23:15** C2-VALIDATE → <pending>: Full suite passes — 301 passed, 2 skipped, 0 failures. Frontend build succeeds. No regressions from Cycle 2 changes.

- **2026-05-11 17:03** C2-VALIDATE → 76582e4: C2-VALIDATE: completed, merged from opencode worktree

- **2026-05-11 18:04** C3-SELECTION → 15d34a7: C3-SELECTION: completed, merged from opencode worktree

- **2026-05-11 18:17** C3-SEARCH-UNIVERSAL → 139f020: C3-SEARCH-UNIVERSAL: completed, merged from opencode worktree

- **2026-05-11 18:24** C3-AI-QUALITY → 2f237b8: C3-AI-QUALITY: completed, merged from opencode worktree

- **2026-05-11 19:09** C3-VALIDATE → febff9e: C3-VALIDATE: completed, merged from opencode worktree

- **2026-05-11 23:57** V2-INFRA-01 → 3b81ea3: V2-INFRA-01: completed, merged from opencode worktree

- **2026-05-12 00:22** V2-INFRA-02 → 44b2ee8: V2-INFRA-02: completed, merged from opencode worktree

- **2026-05-12 00:28** V2-INFRA-03 → c4e6564: V2-INFRA-03: completed, merged from opencode worktree

- **2026-05-12 00:33** V2-INFRA-04 → 15ba92f: V2-INFRA-04: completed, merged from opencode worktree

- **2026-05-12 00:40** V2-INFRA-05 → <pending>: Schema applies cleanly to fresh test DB. All 7 tables present (entities, entity_chunks, entity_events, entity_links, entity_tags, jobs, tags). search_vector generated column verified. HNSW index (entity_chunks_hnsw_idx) confirmed. pgvector <-> operator returns 0 for identical vectors.

- **2026-05-12 00:38** V2-INFRA-05 → 089576a: V2-INFRA-05: completed, merged from opencode worktree

- **2026-05-12 00:50** V2-INFRA-06 → 1b6f350: V2-INFRA-06: completed, merged from opencode worktree

- **2026-05-12 01:00** V2-AUDIT-01 → <pending>: 18 v1 model imports found across 15 files. Inventory matches V2_OVERHAUL_PLAN.md. Acceptance criteria NOT met — cleanup tasks must rewrite these files before V2-CLEANUP-01 can delete old models. Affected: api/batch.py, api/links.py, api/summarize.py, api/review.py, api/daily.py, api/proposals.py, api/summaries.py, services/rollup.py, services/ingestion.py, services/moc.py, services/link_proposer.py, services/links.py, services/extractor.py, services/summarizer.py, services/health_snapshot.py

- **2026-05-12 01:23** V2-AUDIT-01 → ba6c675: V2-AUDIT-01: completed, merged from opencode worktree

- **2026-05-12 07:36** V2-INGEST-01 → 4513c87: V2-INGEST-01: completed, merged from opencode worktree

- **2026-05-12 07:47** V2-INGEST-02 → d713740: V2-INGEST-02: completed, merged from opencode worktree

- **2026-05-12 08:02** V2-SERVICES-01 → 024b220: V2-SERVICES-01: completed, merged from opencode worktree

- **2026-05-12 08:06** V2-SERVICES-02 → 2f88b83: V2-SERVICES-02: completed, merged from opencode worktree

- **2026-05-12 08:09** V2-SERVICES-03 → a801a20: V2-SERVICES-03: completed, merged from opencode worktree

- **2026-05-12 08:19** V2-SERVICES-04 → f109f22: V2-SERVICES-04: completed, merged from opencode worktree

- **2026-05-12 08:34** V2-SERVICES-05 → 4fe9745: V2-SERVICES-05: completed, merged from opencode worktree

- **2026-05-12 08:44** V2-SERVICES-06 → 4069c30: V2-SERVICES-06: completed, merged from opencode worktree

- **2026-05-12 08:54** V2-SERVICES-07 → 323ed17: V2-SERVICES-07: completed, merged from opencode worktree

- **2026-05-12 08:59** V2-SERVICES-08 → bbeac42: V2-SERVICES-08: completed, merged from opencode worktree

- **2026-05-12 10:03** V2-SERVICES-09 → 6066fd4: V2-SERVICES-09: completed, merged from opencode worktree

- **2026-05-12 11:01** V2-SERVICES-10 → 85a7db4: V2-SERVICES-10: completed, merged from opencode worktree

- **2026-05-12 11:25** V2-SERVICES-11 → cde03ec: V2-SERVICES-11: completed, merged from opencode worktree

- **2026-05-12 11:32** V2-API-01 → 8dc3766: V2-API-01: completed, merged from opencode worktree

- **2026-05-12 12:20** V2-API-02 → bb3098a: V2-API-02: completed, merged from opencode worktree

- **2026-05-12 12:32** V2-API-03 → 658f0e4: V2-API-03: completed, merged from opencode worktree

- **2026-05-12 12:40** V2-API-04 → 595aa11: V2-API-04: completed, merged from opencode worktree

- **2026-05-12 12:47** V2-TEST-01 → 79e8e47: V2-TEST-01: completed, merged from opencode worktree

- **2026-05-12 12:55** V2-TEST-02 → fb31cfc: V2-TEST-02: completed, merged from opencode worktree

- **2026-05-12 13:00** V2-TEST-03 → b9632b4: V2-TEST-03: completed, merged from opencode worktree

- **2026-05-12 13:47** V2-TEST-04 → 68df6d60: V2-TEST-04: completed, merged from opencode worktree

- **2026-05-12 13:50** V2-TEST-05 → c2d257cf: V2-TEST-05: completed, merged from opencode worktree

- **2026-05-12 14:05** V2-CLEANUP-01 → e964542d: V2-CLEANUP-01: completed, merged from opencode worktree

- **2026-05-12 14:07** V2-CLEANUP-02 → 33637e64: V2-CLEANUP-02: completed, merged from opencode worktree

- **2026-05-12 14:24** V2-CLEANUP-03 → 47c9ed36: V2-CLEANUP-03: completed, merged from opencode worktree

- **2026-05-12 14:27** V2-CLEANUP-04 → 21abc1ec: V2-CLEANUP-04: completed, merged from opencode worktree

- **2026-05-12 14:35** V2-CLEANUP-05 → 94a93777: V2-CLEANUP-05: completed, merged from opencode worktree

- **2026-05-12 14:40** V2-CLEANUP-06 → 801dcc88: V2-CLEANUP-06: completed, merged from opencode worktree


---
## V3 — Build Plan Execution
> Plan: V3_PLAN.md (Claude Design handoff)
> Started: 2026-05-12
> Executor: codex (primary), opencode/claude/cursor (fallback)
> Source: prd.json (28 tasks, Phase 0-5)


- **2026-05-12 18:18** V3-0.1 → 4eceb0a8: V3-0.1: completed, merged from codex worktree

- **2026-05-12 18:31** V3-0.2 → daca5e00: V3-0.2: completed, merged from codex worktree

- **2026-05-12 18:36** V3-0.3 → c9e50e5b: V3-0.3: completed, merged from codex worktree

- **2026-05-12 18:41** V3-0.4 → 2c0a9074: V3-0.4: completed, merged from codex worktree

- **2026-05-12 18:51** V3-0.5 → 75df988b: V3-0.5: completed, merged from codex worktree

- **2026-05-12 18:56** V3-1.1 → e6ed3699: V3-1.1: completed, merged from codex worktree

- **2026-05-12 19:01** V3-1.2 → 0b40ec83: V3-1.2: completed, merged from codex worktree

- **2026-05-12 19:11** V3-1.3 → b314c33f: V3-1.3: completed, merged from codex worktree
