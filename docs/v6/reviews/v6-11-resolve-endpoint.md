## Review: v6-11-resolve-endpoint

**Verdict:** APPROVE

**Pass 1 — Spec conformance:** PASS
- `api/v4/reports.py` implements `GET /reports?status=pending` (plus `partial`, `reviewed`, `superseded`, `all`), `GET /reports/<id>`, and `POST /reports/<id>/resolve` per SOLUTION_DESIGN §6 and §8.2.
- Resolve body matches the spec: `{decisions: [{suggestion_id, action, edits?, dismissal_reason?}], accept_rest: bool}`.
- All explicit decisions are processed inside one `ChangeBatch`; `accept_rest` applies the remainder atomically.
- `later` leaves the suggestion pending and sets report status to `partial`; full review sets `reviewed` and marks the source note review resolved.
- Undo of a review reverts the `ChangeBatch`, re-opens accepted suggestions to `pending`, and restores the report to `pending` (TEST_PLAN TC-15).
- Dismissals are retained: `_undo_change_batch` skips `suggestion_dismissed` events, and the suggestion stays `dismissed`.
- Tests cover TC-14 (atomicity + rollback), TC-15 (undo retains dismissals), TC-16 (`later` → partial → final resolve), and EC-07 (older report does not resurrect stale values).
- Note: `POST /reports/<id>/undo` is implemented even though SOLUTION_DESIGN §8.2 only lists resolve; it is required to satisfy TC-15 and the existing `ChangeBatch` undo contract.

**Pass 2 — PREAMBLE conformance:** PASS
- The diff is surgical: reports API implementation, ChangeBatch-event migration, model/schema wiring, and integration tests.
- No speculative abstractions or out-of-scope UI/eval work.
- One necessary scope-adjacent addition: `scripts/migrations/007_change_batch_events.sql` links `entity_events` to `change_batches` so the whole review is one undoable unit. It is additive-only (nullable FK + partial index) and idempotent, consistent with migration rules.

**Pass 3 — Skill conformance (TDD / incremental-implementation):** PASS
- New behavior is covered by new tests in `tests/integration/test_v4_reports.py`; no existing tests were modified to make new ones pass.
- One logical implement commit (`v6-11-resolve-endpoint: Reports HTTP API + batch resolve`); review fixes are tracked separately below.

**Pass 4 — Adversarial read:** PASS
- Fixed during review: the `update_unresolved` resolution path calls `_create_activity_update_note` and `_apply_activity_update_policy`, which wrote `activity_update_added` and `ai_updated` events without `change_batch_id`. Undoing a report with such an item would leave the activity-update note and its auto-applied status changes in place instead of reverting them.
  - Fix: threaded optional `change_batch_id` through `_create_activity_update_note`, `_refresh_delegation_cadence`, and `_apply_activity_update_policy` in `api/v4/_shared.py`, and passed the batch ID from `api/v4/reports.py::_resolve_update_unresolved`.
  - Added regression test `test_undo_report_update_unresolved_reverts_activity_update`.
- Validation of inputs: resolve validates action values, duplicate decisions, and that every referenced suggestion is pending in the report before touching the database.
- Rollback on failure: any exception during resolve triggers `db.session.rollback()` and returns 500, leaving suggestions pending and no partial `ChangeBatch`.
- Date parsing uses `_parse_datetime_or_error`; status validation uses `_validate_status`; properties validation uses `_validate_properties`.
- Edge case: resolving a `superseded` report returns 409; resolving with no source note returns 404.

**Pass 5 — Verification reproduction:** PASS
- Focused: `TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest tests/integration/test_v4_reports.py -q` — 10 passed.
- Full backend suite (from worktree with `OPENAI_API_KEY` set to match the canonical `.env` environment): 529 passed, 20 skipped, 0 failed.
- Full backend suite via `bash scripts/v6_validate_slice.sh` (run from `/Volumes/lex1t/dev/shared/repos/engram` after copying changed files for the venv path): 529 passed, 20 skipped, 0 failed; `== slice validation OK ==`.
- Note: running the suite from the worktree without `OPENAI_API_KEY` exposed 3 semantic-search failures because `services.embeddings.embed_query` returns `None` when the key is absent. These are environment-level, not product regressions; the canonical validation commands run from the main repo where `.env` supplies the key.
- `bash scripts/v6_check_review_verdict.sh v6-11-resolve-endpoint` exits 0.

**Fixes applied in this review:**
- `api/v4/_shared.py`: added optional `change_batch_id` parameter to `_create_activity_update_note`, `_refresh_delegation_cadence`, and `_apply_activity_update_policy`; passed it through to every `_write_event` they emit.
- `api/v4/reports.py`: `_resolve_update_unresolved` now passes `change_batch_id` into the activity-update helpers so undo reverts the full batch.
- `tests/integration/test_v4_reports.py`: added `test_undo_report_update_unresolved_reverts_activity_update`; imported `EntityEvent` and `EntityLink` at module level.

**Required changes before merge:** None.

**Optional suggestions (non-blocking):**
- Document the `POST /reports/<id>/undo` route in `SOLUTION_DESIGN.md` §8.2 or consider reusing a generic batch-undo endpoint in a future slice.
- Consider adding a test for decision-creation via resolve and for edit-action validation on unsupported operation types.

**Reviewer:** opencode (v6-11-code-review)
