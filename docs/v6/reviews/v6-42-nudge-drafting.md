## Review: v6-42-nudge-drafting

**Verdict:** APPROVE

**Pass 1 — Spec conformance:** PASS
- Notes: the slice delivers V6-42 per `docs/v6/IMPLEMENTATION_PLAN.md` and TC-44 / UC-7 (draft portion) in `docs/v6/TEST_PLAN.md`. `POST /api/v4/commitments/<id>/nudge-draft` is registered via `api/v4/commitments.py` (imported in `api/v4/__init__.py`) with business logic in `services/v4_nudge_draft.py`. Receipt gathering pulls original ask (task title), committed date (task/source-note heuristic), owner, space, source-note quote, and last activity update via EntityLink relationships. Response includes `draft`, `original_ask`, `committed_at`, `receipts`, and explicit `auto_sent: false` (TC-44). LLM path uses receipt-grounded system prompt with JSON response; heuristic fallback when LLM disabled or fails. UI: `NudgeDraftAffordance` in `TypedAffordances.jsx` provides draft load, editable textarea, and copy button; wired on Workboard waiting-on rows (`showNudge={item.states?.waiting_on}`) and Dossier "Waiting on others" section. Client method `v4API.commitments.nudgeDraft`. UC-7 "nudged logged" and reply reconciliation are explicitly out of scope for this slice (draft-only per acceptance criteria and SOLUTION_DESIGN §8 endpoint contract).

**Pass 2 — PREAMBLE conformance:** PASS
- Notes: 16 files changed, all trace to nudge drafting endpoint + UX. Service layer owns context gathering, prompt building, and draft generation; API handler is thin (404 on missing commitment, jsonify payload). No drive-by refactors. Prompt fixture corpus (`tests/fixtures/nudge_draft_corpus.json`) exercises LLM prompt shape without live API calls. No new npm dependencies. Heuristic fallback is minimum viable path when LLM unavailable in tests/production, not speculative abstraction.

**Pass 3 — Skill conformance (tdd / incremental-implementation):** PASS
- Notes: single commit `8ad20c55` implements the full slice. Unit tests cover prompt serialization, heuristic draft, corpus fixtures, and receipt gathering from links (`tests/unit/test_v4_nudge_draft.py`). Integration tests cover TC-44 payload shape, no auto-send/mutation, mocked LLM path, and 404 (`tests/integration/test_v4_nudge_draft.py`). UI Vitest covers TaskAffordances nudge flow, NudgeDraftAffordance copy, Workboard waiting-on affordance visibility, and Dossier waiting-on button (`TypedAffordances.test.jsx`, `WorkboardSurface.test.jsx`, `DossierSurface.test.jsx`). No existing tests weakened. Implement-task validation passed per `prd.json` evidence.

**Pass 4 — Adversarial read:** PASS
- Findings: no blocking defects. Minor non-blocking observations: (1) `_committed_at` prefers `task.created_at` over source-note date — reasonable default but may not match the user's mental "committed date" when task was created before the capturing note; receipts still include source-note quote separately. (2) `last_update` receipt uses `task.id` as `entity_id` rather than the activity note id — cosmetic metadata only; label/value are correct. (3) Draft endpoint does not write `entity_events` — intentional draft-only; "nudged" logging deferred to a future slice. (4) LLM failures are logged and silently fall back to heuristic — acceptable; user still gets a usable draft. (5) `_llm_enabled()` returns True outside Flask app context (`RuntimeError` branch) — only relevant for ad-hoc scripts, not API path. (6) Dossier shows nudge on all waiting-on tasks regardless of ripeness threshold; Workboard gates on `states.waiting_on` — consistent with each surface's data model.

**Pass 5 — Verification reproduction:** PASS
- Commands run: `TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test OPENAI_API_KEY=dummy PYTHONPATH=. /Volumes/lex1t/dev/shared/repos/engram/venv/bin/pytest tests/unit/test_v4_nudge_draft.py tests/integration/test_v4_nudge_draft.py -q`; `cd ui && npm test -- TypedAffordances WorkboardSurface DossierSurface`; `OPENAI_API_KEY=dummy bash scripts/v6_validate_slice.sh`; `bash scripts/v6_check_review_verdict.sh v6-42-nudge-drafting` (after writing this file).
- Result: nudge backend — 8/8 passed. UI — 3 files, 14 tests passed (including nudge draft + copy flows). Full backend suite — 617 passed, 20 skipped (`slice validation OK`). Verdict script exits 0.

**Fixes applied in this review:** none

**Required changes before merge:** none

**Optional suggestions (non-blocking):**
- Log a `nudged` entity event when the user copies or confirms a draft (UC-7 remainder) in a follow-up slice.
- Use the activity note id in the `last_update` receipt `entity_id` field for accurate citation links.
- Consider preferring source-note `created_at` over task `created_at` in `_committed_at` when a derived-from note exists.
