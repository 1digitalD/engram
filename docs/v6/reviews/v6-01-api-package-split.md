## Review: v6-01-api-package-split

**Verdict:** APPROVE

**Pass 1 — Spec conformance:** PASS
- `api/v4_entities.py` deleted; routes live under `api/v4/` package with blueprint assembly in `api/v4/__init__.py`.
- `api/__init__.py` imports route modules from `api.v4`.
- Stub modules exist for `reports`, `workboard`, `markers` (Phase 1+ homes).
- Route table matches baseline (57 routes after V6-02 operator endpoints added).
- Full backend suite green with zero test file edits from the original split commit.
- Compatibility shim at `api/v4_entities/__init__.py` re-exports `_shared` for existing test patch paths.

**Pass 2 — PREAMBLE conformance:** PASS
- Mechanical refactor; route handlers moved to domain modules.
- Shared helpers consolidated in `api/v4/_shared.py` (expected for Phase 0 — further decomposition is Phase 1+ work, not a Phase 0 requirement).
- No behavior or response-shape changes observed in integration tests.

**Pass 3 — Skill conformance (TDD / incremental):** PASS
- Single coherent implement commit (`7a4ab3a2`) with validation green.
- `_v4e` shim imports in `capture.py` and `insights.py` are **required** — tests patch `api.v4_entities.*` (see `test_v4_capture.py`, `test_v4_threads.py`, `test_v4_decisions.py`).

**Pass 4 — Adversarial read:** PASS
- Removed unused `_v4e` imports from `system.py`, `entities.py`, `links.py`, `today.py`, `recall.py` (retro fix — no behavioral change).
- Circular-import guards in `_shared.py` (`_extract_decision_candidates`, `_append_decision_suggestions`) must remain on the `api.v4_entities` shim path; direct calls break test mocks.
- Blueprint registration order via explicit submodule imports in `api/v4/__init__.py` is correct.

**Pass 5 — Verification reproduction:** PASS
- `CHECK_ROUTES=1 bash scripts/v6_validate_slice.sh` — 512 passed, 20 skipped; route table OK.

**Fixes applied in this review:**
- Removed dead `_v4e` imports from five route modules (no `_v4e` usage).

**Required changes before merge:** None.

**Optional suggestions (non-blocking):**
- `_shared.py` (~5.3k lines) is the remaining concentration of logic; future phases should move helpers into `services/` as new behavior is added, not grow `_shared` further.
- Document the `api.v4_entities` shim contract in `api/v4_entities/__init__.py` module docstring (done).

**Reviewer:** overseer (Phase 0 retro review, 2026-07-08)
