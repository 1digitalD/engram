## Review: v6-41-today-surface

**Verdict:** APPROVE

**Pass 1 — Spec conformance:** PASS
- Notes: the slice delivers V6-41 per `docs/v6/IMPLEMENTATION_PLAN.md` and UC-6 in `docs/v6/TEST_PLAN.md`. `GET /api/v4/today` is extended via `services/v4_today.extend_today_payload()` (hooked from `_build_today_payload` in `api/v4/_shared.py`) with `needs_you`, `in_motion`, `counts`, `ripened_follow_ups`, and `newly_at_risk` without breaking legacy bucket keys. Needs-you vs in-motion partitioning covers overdue/due-today/follow-ups, blocked/waiting, fired markers, ripened follow-ups (from `delegations_quiet`), dependency interventions, pending suggestions, and newly-at-risk items; in-motion covers upcoming due/follow-ups, recent notes, and stale/archival projects. UI: `TodaySurface.jsx` loads `v4API.today()`, renders both columns with counts, and is wired at `/next/today` as the default landing route (`NextApp.jsx`, nav enabled in `NextShell.jsx`). Daily at-risk snapshot job (`today_at_risk_snapshot`) is registered and bootstrapped on app start; TC-43 diff logic excludes items present in yesterday's snapshot. Acceptance criteria satisfied: extended feed load, section counts, fired markers + ripened follow-ups visible, component tests pass.

**Pass 2 — PREAMBLE conformance:** PASS
- Notes: 12 files changed, all trace to Today surface + feed extension. Service layer owns partitioning, ripened follow-up shaping, and snapshot logic; API change is a four-line hook. No drive-by refactors, no speculative abstractions beyond the required snapshot job handler. UI follows existing `/next` surface patterns (CSS modules, vocab helpers, mocked API tests). No new npm dependencies.

**Pass 3 — Skill conformance (tdd / incremental-implementation):** PASS
- Notes: single commit `03a6249f` implements the full slice. Unit tests cover partitioning and snapshot diff (`tests/unit/test_v4_today.py`); integration tests cover extended payload shape and TC-43 newly-at-risk diff (`tests/integration/test_v4_today.py`); Vitest covers load, counts, fired markers, ripened follow-ups, and in-motion rows (`TodaySurface.test.jsx`). No existing tests were weakened. Implement-task validation (`npm test -- next`, `npm run build`, `v6_validate_slice.sh`) passed per `prd.json` evidence.

**Pass 4 — Adversarial read:** PASS
- Findings: no blocking defects. Minor non-blocking observations: (1) `NEEDS_YOU_KINDS` in `services/v4_today.py` is defined but unused — harmless dead constant. (2) `itemPath()` for tasks without a linked project/area yields `/next/spaces/` with an empty segment — edge case; most Today items carry parent context from the API. (3) `compute_newly_at_risk()` returns an empty list until the first snapshot exists (cold start) — intentional per unit test; the bootstrap job schedules capture after 10 minutes. (4) Operator-identity partitioning sends non-operator-assigned overdue/due items to in-motion while blocked/waiting always land in needs-you — matches the "mine vs delegated" triage model and is covered by backend partitioning logic. (5) `pending_suggestions` collapses to a single summary row rather than one row per suggestion — acceptable UX compression for the Today queue.

**Pass 5 — Verification reproduction:** PASS
- Commands run: `cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test -- next`; `TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test PYTHONPATH=. /Volumes/lex1t/dev/shared/repos/engram/venv/bin/pytest tests/unit/test_v4_today.py tests/integration/test_v4_today.py::test_v4_today_extended_feed_includes_sections_and_counts tests/integration/test_v4_today.py::test_tc43_newly_at_risk_diff_uses_daily_snapshot -q`; `bash scripts/v6_check_review_verdict.sh v6-41-today-surface` (after writing this file).
- Result: UI — 8 files, 34 tests passed (including 3 TodaySurface tests). Backend — 5/5 focused today tests passed. Verdict script exits 0.

**Fixes applied in this review:** none

**Required changes before merge:** none

**Optional suggestions (non-blocking):**
- Remove unused `NEEDS_YOU_KINDS` constant or use it for validation/documentation.
- Guard `itemPath()` against empty space id so task rows without parent context render as plain text instead of a broken link.
- Consider surfacing a "warming up" hint when `newly_at_risk` is empty because no snapshot exists yet (first deploy UX).
