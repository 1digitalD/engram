## Review: v6-10-report-assembler

**Verdict:** APPROVE

**Pass 1 — Spec conformance:** PASS
- Migration `006_distillation_reports.sql` creates `distillation_reports` table and adds nullable `ai_suggestions.report_id` FK, matching SOLUTION_DESIGN §5.1.
- `services/v4_report.py` groups all pending candidates from one capture under one `distillation_reports` row and links every suggestion via `report_id`.
- Section ordering is stable: routing summary → applied annotations → proposed commitments → decisions → questions → leftovers (TEST_PLAN TC-11).
- Speaker-less commitment candidates become attribution questions with `owner: null` (TC-12); owned commitments land in proposed commitments.
- Re-distill supersedes prior reports and expires their pending suggestions while leaving resolved suggestions untouched (TC-17).
- Tests cover TC-10..13 and TC-17 in both unit and integration form.
- Route stub in `api/v4/reports.py` was not required for this slice; HTTP surface ships in V6-11 per task description.

**Pass 2 — PREAMBLE conformance:** PASS
- Surgical change set: one migration, one service module, two test files, model/schema wiring, and job-worker registration in `api/v4/_shared.py`/`app.py`.
- No speculative abstractions or out-of-scope features; the assembler is pure grouping with no auto-create or resolve logic.
- No drive-by refactors of adjacent capture/reconciliation code.

**Pass 3 — Skill conformance (TDD / incremental-implementation):** PASS
- New behavior is covered by new tests (`tests/unit/test_v4_report.py`, `tests/integration/test_v4_reports.py`); no existing tests were modified to make new ones pass.
- One logical commit for the implement slice; review fixes are separate edits tracked below.

**Pass 4 — Adversarial read:** PASS
- Review fixes applied:
  1. Routing-summary receipt had `length: len(note_content)` but `quote: note_content[:200]`, so notes > 200 chars produced inconsistent offsets. Fixed to quote and length both capped at 200 chars, with regression test.
  2. Removed unused `import pytest` orphan in `tests/unit/test_v4_report.py`.
- Null handling verified at boundaries: `_getattr`/`_find_text_offset` tolerate missing `content`, `payload`, `reason`, and `title`.
- `supersede_prior_reports` filters by active statuses and only expires `pending` suggestions from prior reports, preserving resolved ones.
- `assemble_report_for_note` returns `None` for missing notes and for captures with no candidates/events, logging appropriately.
- Duplicate job enqueue guard in `queue_assemble_report_job` is best-effort (no `FOR UPDATE`); acceptable for a background assembler because re-running supersedes rather than duplicates meaningful state.

**Pass 5 — Verification reproduction:** PASS
- Focused: `TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest tests/unit/test_v4_report.py tests/integration/test_v4_reports.py -q` — 9 passed.
- Full backend suite (worktree, with `OPENAI_API_KEY` supplied to match the canonical `.env` environment): 521 passed, 20 skipped, 0 failed.
- `bash scripts/v6_check_review_verdict.sh v6-10-report-assembler` exits 0.

**Fixes applied in this review:**
- `services/v4_report.py`: cap routing-summary receipt quote and length to 200 chars consistently.
- `tests/unit/test_v4_report.py`: remove unused `pytest` import; add `test_routing_summary_receipt_quote_matches_length` regression test.

**Required changes before merge:** None.

**Optional suggestions (non-blocking):**
- Document in `supersede_prior_reports` docstring that it does not commit; callers must commit the enclosing transaction.
- Consider adding `FOR UPDATE SKIP LOCKED` to `queue_assemble_report_job` duplicate check if enqueue races become observable under load.

**Reviewer:** opencode (v6-10-code-review)
