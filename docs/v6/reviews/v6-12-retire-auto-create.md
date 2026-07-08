## Review: v6-12-retire-auto-create

**Verdict:** APPROVE

**Pass 1 — Spec conformance:** PASS
- `AUTO_CREATE_THRESHOLD` logic is removed (not set to 1.0) per SOLUTION_DESIGN §7.1 and IMPLEMENTATION_PLAN V6-12.
- Deleted from `api/v4/_shared.py`: `_auto_create_entity`, `_can_auto_create_entity`, `_task_auto_create_ok`, and the `AUTO_CREATE_ENTITY_CONFIDENCE` constant.
- All risky entity-creation candidates (task, project, area, resource, person) now route to the review queue as `AiSuggestion` proposals inside a `DistillationReport`.
- `_process_capture_extraction` and `_reconcile_capture_candidates` now synchronously assemble a report and return `report_id`.
- `POST /capture`, capture SSE stream, `POST /entities/<id>/ingest_candidates`, and `POST /entities/<id>/reprocess` all include `report_id` in their payloads.
- Annotate-tier applied changes (tags, links, summaries) appear in report narrative sections with `event_id`, satisfying TC-13's undoable report-line requirement.
- Tests cover TC-18 (0.95-confidence create candidate → proposal only, no entity row, no `agent:*` creation event) and verify existing capture suites still pass.

**Pass 2 — PREAMBLE conformance:** PASS
- The diff is surgical: auto-create deletion, report_id plumbing, result-payload updates, MCP formatter update, and test contract adjustments.
- No speculative abstractions or out-of-scope features.
- Review cleanup is minimal: renamed a leftover threshold constant and updated stale comments/test names (see fixes below).

**Pass 3 — Skill conformance (TDD / incremental-implementation):** PASS
- New tests (`test_capture_retired_auto_create_becomes_proposal`, updated `test_capture_response_contract_preserves_baseline_shape`) describe the retired behavior.
- Existing tests were updated to assert the new contract (proposals instead of auto-created entities), not weakened to make new tests pass.
- One logical implement commit (`v6-12-retire-auto-create: Retire auto-create; annotate lines in report`); review fixes are tracked below.

**Pass 4 — Adversarial read:** PASS
- Verified the auto-create path is deleted, not disabled: the helper functions and confidence constant are gone, and the conditional branch that called `_can_auto_create_entity` is replaced by a single suggestion-creation path.
- `_task_suggest_ok` now treats score-4 candidates as proposals, so high-confidence structurally-perfect tasks no longer bypass review.
- Near-duplicate scoring (`NEAR_DUPLICATE_SCORE`) still routes plausible duplicates to review instead of treating them as new entities.
- Synchronous report assembly (`_assemble_report_for_note_sync`) replaces the previous job-queue path, ensuring `report_id` is available in the capture response.
- The MCP formatter handles the new `report_id` field without leaking internal IDs.

**Pass 5 — Verification reproduction:** PASS
- Focused: `TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest tests/integration/test_v4_capture.py tests/integration/test_v4_reports.py -q` — 16 passed.
- Full backend suite: 527 passed, 20 skipped, 0 failed (run with `OPENAI_API_KEY=dummy` so `embed_query` does not short-circuit mocked semantic-search tests).
- `bash scripts/v6_validate_slice.sh` (with `OPENAI_API_KEY=dummy`) prints `== slice validation OK ==`.
- Grep confirms zero `AUTO_CREATE`, `_can_auto_create`, `_task_auto_create`, or `_auto_create_entity` references in `.py` files.
- `bash scripts/v6_check_review_verdict.sh v6-12-retire-auto-create` exits 0.

**Fixes applied in this review:**
- `services/v4_reconciliation.py`: renamed the leftover `AUTO_CREATE_CONFIDENCE_THRESHOLD` constant to `UNCERTAINTY_CONFIDENCE_THRESHOLD`; updated its comment and the `is_uncertain_decision` docstring to state that auto-create is retired and the threshold now only affects "AI was not sure" narrative labeling in the review queue.
- `services/v4_reconciliation.py`: updated a stale comment that still described near-duplicate routing as "refuse to auto-create".
- `api/v4/_shared.py`: updated the `_link_task_to_note_projects` docstring from "newly auto-created task" to "newly accepted task" to match its current call sites (suggestion/report acceptance).
- `tests/integration/test_v4_capture_extraction.py`: renamed misleading test names/docstrings that referenced the retired auto-create path/threshold (`test_capture_auto_created_task_applies_assigned_to_person_link`, `test_capture_drops_bare_person_below_auto_create_threshold`, `test_capture_auto_created_task_links_to_source_note_projects`).

**Required changes before merge:** None.

**Optional suggestions (non-blocking):**
- Consider removing the dead `auto_created` boolean from activity-update extracted-task payloads (`api/v4/_shared.py` and `mcp_server/v4_formatters.py`) in a future cleanup slice, since it is always `False` after auto-create retirement.
- Consider renaming the `_queue_embed_job(person.id, "assignee_auto_create")` job reason string to remove the "auto_create" term, though it is not user-facing threshold logic.

**Reviewer:** opencode (v6-12-code-review)
