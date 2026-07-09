## Review: v6-50-themes

**Verdict:** APPROVE

**Pass 1 — Spec conformance:** PASS
- Notes: The slice matches the V6-50 scope in `prd.json`, [docs/v6/IMPLEMENTATION_PLAN.md](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-50-code-review-codex-a116-codex/docs/v6/IMPLEMENTATION_PLAN.md:98), and [docs/v6/SOLUTION_DESIGN.md](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-50-code-review-codex-a116-codex/docs/v6/SOLUTION_DESIGN.md:141). Theme support is added to shared entity/status validation and relationship compatibility in [api/v4/_shared.py](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-50-code-review-codex-a116-codex/api/v4/_shared.py:28), the additive DB constraint migration is present in [scripts/migrations/011_theme_type.sql](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-50-code-review-codex-a116-codex/scripts/migrations/011_theme_type.sql:1), promotion is implemented as a dedicated `theme -> project` endpoint with conflict handling and a `promoted` event in [api/v4/entities.py](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-50-code-review-codex-a116-codex/api/v4/entities.py:414), and `/convert` is explicitly retired. Coverage for TC-50..52 and EC-24 is added in [tests/integration/test_v4_themes.py](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-50-code-review-codex-a116-codex/tests/integration/test_v4_themes.py:1).

**Pass 2 — PREAMBLE conformance:** PASS
- Notes: The diff stays focused on the requested backend slice: one migration, shared type/status wiring, one API endpoint, narration support, and targeted tests. Business logic remains in the existing service/API layers without speculative abstraction. The only non-product-file edits are the expected tracker and `prd.json` status updates.

**Pass 3 — Skill conformance (tdd, incremental-implementation):** PASS
- Notes: The implement slice landed as a single logical commit (`1c33fe1f v6-50: themes backend + promote (overseer)`) and includes focused regression/integration coverage for the new behavior in [tests/integration/test_v4_themes.py](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-50-code-review-codex-a116-codex/tests/integration/test_v4_themes.py:43), plus narration coverage in [tests/unit/test_v4_narration.py](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-50-code-review-codex-a116-codex/tests/unit/test_v4_narration.py:236). Existing tests were narrowed only where the contract changed: [tests/integration/test_v4_merge.py](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-50-code-review-codex-a116-codex/tests/integration/test_v4_merge.py:147) now asserts the retired endpoint behavior instead of preserving obsolete conversion flows.

**Pass 4 — Adversarial read:** PASS
- Findings: No blocking correctness issues found. Promotion checks the entity exists, rejects deleted and non-theme entities, prevents project-title collisions, preserves entity identity while flipping type/status, records a typed event, and re-queues embeddings in [api/v4/entities.py](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-50-code-review-codex-a116-codex/api/v4/entities.py:414). Theme relationship compatibility is extended coherently across mentions/references/related in [api/v4/_shared.py](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-50-code-review-codex-a116-codex/api/v4/_shared.py:101). The new tests also assert that links and decisions survive promotion and that workboard excludes themes from project/task commit-state groupings in [tests/integration/test_v4_themes.py](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-50-code-review-codex-a116-codex/tests/integration/test_v4_themes.py:50).

**Pass 5 — Verification reproduction:** PASS
- Commands run: `TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test OPENAI_API_KEY=dummy PYTHONPATH=. /Volumes/lex1t/dev/shared/repos/engram/venv/bin/pytest tests/integration/test_v4_themes.py -q`; `OPENAI_API_KEY=dummy bash scripts/v6_validate_slice.sh`; `bash scripts/v6_check_review_verdict.sh v6-50-themes`.
- Result: The verdict check passed from this review worktree. Both pytest commands were re-run here but the sandbox blocks TCP access to the required test Postgres on `localhost:5433` (`psycopg2.OperationalError: Operation not permitted` during fixture setup), so I could not independently reproduce the recorded green test runs from `prd.json` inside this environment.

**Fixes applied in review:** none

**Required changes before merge:** none

**Optional suggestions (non-blocking):**
- Remove the now-unreachable legacy `convert_entity` implementation body left below the early `410` return in [api/v4/entities.py](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-50-code-review-codex-a116-codex/api/v4/entities.py:473) once no follow-up slice needs it for reference.
