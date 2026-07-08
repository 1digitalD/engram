## Review: v6-32-amend-archive-redact-delete

**Verdict:** APPROVE

Reviewed commit: c7d04e71 (`v6-32-amend-archive-redact-delete: Amend, archive, redact, delete`), 8 files, +385/−15.

**Pass 1 — Spec conformance:** PASS
- Notes: all five acceptance criteria are satisfied.
  - Migration 009: `scripts/migrations/009_redacted_lifecycle.sql` extends `chk_entities_lifecycle` with `redacted` and adds `redacted` to `entity_events_event_type_check`; idempotent drops/recreates. `test_migration_009_applies_cleanly` asserts the constraint definition contains `redacted`.
  - TC-34 amend: PATCH on an activity-update note with changed `content` writes an `updated` event with `reason="amended"`, `old_value.content` and `new_value.content` populated (`api/v4/entities.py:203-238`; `test_tc34_amend_activity_update_records_old_and_new_content`).
  - TC-35 archive/delete: PATCH `lifecycle=archived` is reversible via PATCH back to `active`, writes an `archived` event with lifecycle old/new, and archived tasks drop off Workboard (`services/v4_workboard.py` filters `Entity.lifecycle == "active"`). DELETE tombstones with `lifecycle=deleted` and a `deleted` event — no hard row removal.
  - TC-36 redact: `POST /entities/<id>/redact` tombstones title/content, sets `lifecycle=redacted`, deletes `EntityChunk` rows, writes `redacted` event with `old_value=None`, excludes note from semantic search, and surfaces `citation_state=redacted` + label on citing entities (`api/v4/entities.py:316-339`, `api/v4/_shared.py:1628-1630`).
  - EC-22: redacting a source note keeps the commitment entity and `derived_from` link intact; detail view shows redacted citation label (`test_ec22_redacted_source_note_keeps_commitment_and_shows_redacted_receipt`).
- Bonus (beyond acceptance criteria, not blocking): EC-23 person-delete guard (`test_ec23_delete_person_with_open_tasks_is_blocked`), non-note redact rejection (`test_redact_rejects_non_notes`). EC-20/EC-21 from the task description are not covered in this slice — deferred to later manipulation/concurrency work; not listed in acceptance criteria.
- No out-of-scope items shipped; no criterion was weakened.

**Pass 2 — PREAMBLE conformance:** PASS
- Notes: minimum surface area — one migration, lifecycle helpers in `_shared.py`, redact endpoint + amend/archive/delete refinements in `entities.py`, narration template for `redacted`, model constraint sync. No speculative abstractions. Constants (`REDACTED_TOMBSTONE`, `REDACTED_TITLE`, `REDACTED_CITATION_LABEL`) are single-use labels, not a framework. No TODOs, no commented-out code, no swallowed exceptions. Default entity list now excludes `redacted` alongside `deleted` (`entities.py:36`) — required for redact semantics, not drive-by cleanup.

**Pass 3 — Skill conformance (tdd / incremental-implementation):** PASS
- Notes: tests and implementation land in one commit; test names describe behavior (`test_tc34_amend_activity_update_records_old_and_new_content`, `test_tc36_redact_note_tombstones_content_removes_chunks_and_breaks_citations`). Existing tests were not modified to mask failures. Commit message references the task id (v6-32). Single-commit slice matches acceptance criteria. Module-scoped migration fixture applies 009 once for the test module — appropriate for integration coverage without polluting other suites.

**Pass 4 — Adversarial read:** PASS
- Findings (all verified non-blocking):
  - Amend scope is intentionally narrow: only notes with `source == "activity_update"` get the content-only amend event; other content edits still emit full-snapshot `updated` events. Matches TC-34's activity-update path and avoids leaking old content into events for non-amend edits.
  - Archive via PATCH emits both a generic `updated` event (full snapshot) and a dedicated `archived` event — consistent with pre-existing PATCH event patterns and gives Workboard/Ledger both granular and summary signals.
  - Redact is idempotent: already-redacted notes return 200 with current data, no duplicate event (`entities.py:323-324`).
  - Redact event carries no old content (`old_value=None`) — satisfies privacy requirement; chunks are hard-deleted before commit so vector search cannot resurrect content.
  - `_archive_incoming_activity_updates` archives linked activity-update notes when parent is archived; `_delete_incoming_activity_updates` hard-deletes them on parent delete — asymmetric but intentional (archive reversible, delete tombstone).
  - `_person_has_open_assigned_tasks` checks `assigned_to` links with open/in_progress/waiting/blocked statuses only — done/cancelled tasks do not block person delete.
  - Citation breakage is visible, not silent: redacted sources remain linkable with explicit `citation_state` and label rather than disappearing from detail sections.
  - No off-by-one, race, or resource-leak issues identified in the lifecycle paths reviewed.

**Pass 5 — Verification reproduction:** PASS
- Commands run:
  - `TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test PYTHONPATH=. /Volumes/lex1t/dev/shared/repos/engram/venv/bin/pytest tests/integration/test_v4_lifecycle.py -q` → 7 passed
  - `OPENAI_API_KEY=dummy bash scripts/v6_validate_slice.sh` → 593 passed, 20 skipped
- Result: all lifecycle tests green; full backend suite passes on test DB (:5433). Semantic search tests require `OPENAI_API_KEY` set (mocked embeddings); without it three search tests fail — pre-existing env requirement, not introduced by this slice.

**Fixes applied in this review:** none

**Required changes before merge:** none

**Optional suggestions (non-blocking):**
- Add `POST /api/v4/entities/<id>/redact` to `docs/v6/fixtures/route_table_baseline.txt` before a `CHECK_ROUTES=1` gate run.
- Consider a dedicated narrate template branch for `updated` events with `reason="amended"` so Dossier Ledger can distinguish "content amended" from generic field updates without parsing `reason`.
- EC-20 (concurrent MCP write during resolve) and EC-21 (partial batch revert) remain untested in Phase 3 — track for a later concurrency slice if still required by TEST_PLAN.
