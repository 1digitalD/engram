## Review: v6-40-markers-backend

**Verdict:** APPROVE

**Pass 1 — Spec conformance:** PASS
- Notes: the slice delivers the Phase 4 markers backend per `docs/v6/SOLUTION_DESIGN.md` §5.3 and `docs/v6/IMPLEMENTATION_PLAN.md` V6-40. Additive migration `scripts/migrations/010_followup_markers.sql` matches the schema (kinds, `due_at`, `person_entity_id`, `fired_at`, `resolved_at`) with supporting indexes. CRUD is exposed at `GET/POST/PATCH/DELETE /api/v4/markers` via thin handlers in `api/v4/markers.py` and `services/v4_markers.py`. Due nudge/custom markers fire once into Today (`fired_at` set, no duplicate firing on later cycles — TC-40, EC-16). Discuss markers are excluded from the Today feed and surfaced via `prep_payload_for_person` for meeting prep (TC-41). Markers on archived or done entities auto-resolve without firing (TC-42, EC-15), both in the firing job and on entity archive/status change in `api/v4/entities.py`. Two markers on the same entity/day fire as separate lines (EC-17). EC-18 (operator timezone) is explicitly out of scope for this slice and deferred to later Phase 4 work.

**Pass 2 — PREAMBLE conformance:** PASS
- Notes: the diff is surgical — 13 files, all trace to markers backend. Service layer owns business logic; API handlers stay thin. No drive-by refactors, no speculative abstractions beyond the registered `fire_markers` job handler (required by the task). Existing `/today` payload is extended with `fired_markers` without breaking prior keys.

**Pass 3 — Skill conformance (tdd / incremental-implementation):** PASS
- Notes: single commit `0630232a` implements the full slice. Unit tests cover validation, entity blocking, and idempotent firing; integration tests cover CRUD, TC-40..42, and EC-15..17. No existing tests were weakened to make new ones pass. The implement task's focused pytest command (11 tests) and full `v6_validate_slice.sh` both pass.

**Pass 4 — Adversarial read:** PASS
- Findings: no blocking defects. Minor non-blocking observations: (1) `_validate_marker_payload` error text says "nudge markers" but the `due_at` requirement also applies to `custom` kind — cosmetic only. (2) Partial PATCH can set `kind` to `discuss` without requiring `person_entity_id` — unlikely in normal use and not in acceptance criteria. (3) `GET /today` calls `fire_due_markers` as a side effect — intentional per design (Today load is the firing cycle for tests and UI); the background job provides the same path for unattended runs. (4) Marker CRUD does not write `entity_events` — consistent with SOLUTION_DESIGN, which treats markers as a separate table without audit-event requirements in this slice.

**Pass 5 — Verification reproduction:** PASS
- Commands run: `TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test PYTHONPATH=. /Volumes/lex1t/dev/shared/repos/engram/venv/bin/pytest tests/unit/test_v4_markers.py tests/integration/test_v4_markers.py -q`; `OPENAI_API_KEY=dummy bash scripts/v6_validate_slice.sh` (worktree); `bash scripts/v6_validate_slice.sh` (main repo at same commit `0630232a`).
- Result: 11/11 marker tests passed. Full backend suite: 604 passed, 20 skipped (worktree with `OPENAI_API_KEY=dummy`; main repo green without extra env). `bash scripts/v6_check_review_verdict.sh v6-40-markers-backend` passes after this file is written.

**Fixes applied in this review:** none

**Required changes before merge:** none

**Optional suggestions (non-blocking):**
- Align validation error copy for `custom` kind due_at requirement with the actual check.
- Consider requiring `person_entity_id` when PATCH changes `kind` to `discuss`.
- EC-18 timezone-aware firing belongs in a follow-up slice (V6-41+ or dedicated task).
