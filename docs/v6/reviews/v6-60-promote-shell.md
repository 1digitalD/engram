## Review: v6-60-promote-shell

**Verdict:** APPROVE

**Pass 1 — Spec conformance:** PASS
- Notes: The slice matches V6-60 in `docs/v6/IMPLEMENTATION_PLAN.md` (Phase 6 cutover) and TC-60 in `docs/v6/TEST_PLAN.md`. `App.jsx` is now a thin router: `/` → `NextApp` (v6 shell, default landing `/today`), `/legacy/*` → extracted `LegacyApp` (V5 + lab unchanged), `/next/*` → `NextRedirect` strips the prefix and preserves `search`/`hash`. `LegacyApp.jsx` is a straight extraction of the former `AppShell` with relative child routes; `legacyPath()` centralizes `/legacy` prefixes across TopBar, lab, and V5 views. `docs/DEPLOY.md` documents v6 as default, `/legacy` fallback, `/next` bookmark redirects, and rollback tag `engram/v6-phase-5-complete`. Acceptance criteria satisfied: `/` serves NextApp, `/legacy/*` serves V5 shell, `/next/*` redirects to equivalent v6 routes, UI tests pass.

**Pass 2 — PREAMBLE conformance:** PASS
- Notes: 39 files changed, all trace to shell promotion and path prefixing. No drive-by refactors beyond required route updates (`/next/...` → `/...` in v6 surfaces; V5/lab links → `/legacy/...`). `App.jsx` shrank to 19 lines; legacy behavior preserved in `LegacyApp.jsx` + relocated tests. `legacyPaths.js` is a minimal single-purpose helper. No new dependencies. `prd.json` and `EXECUTION-TRACKER.md` updates are orchestration metadata, not scope creep.

**Pass 3 — Skill conformance (tdd / incremental-implementation):** PASS
- Notes: Single commit `e10d9a34` implements the full slice. New `NextRoutes.test.jsx` covers TC-60 (`/` → v6 today, `/legacy/now` → legacy, `/next/today` → `/today`). Former `App.test.jsx` V5 shell tests moved intact to `LegacyApp.test.jsx` with `/legacy` prefix — behavior coverage preserved, not weakened. Path-only updates in existing next-surface tests (`ReviewSurface`, `DossierSurface`, etc.) align with promoted routes. Implement-task validation (`npm test -- next`, `npm run build`, `v6_validate_slice.sh`) passed per `prd.json` evidence (44 UI tests, 628 backend tests).

**Pass 4 — Adversarial read:** PASS
- Findings: no blocking defects. Non-blocking observations: (1) Root-level V5 routes (`/now`, `/threads`, etc.) no longer exist — intentional cutover; bookmarks must use `/legacy/...` or `/next/...` redirect. (2) `NextRedirect` maps bare `/next` to `/` which then lands on `/today` — correct bookmark-compat behavior. (3) `LabShell` routes switched from absolute (`/lab/today`) to relative (`today`) under the `/legacy/lab/*` mount — correct for nested routing. (4) `ReviewSurface.test.jsx` duration-timing test is intermittently flaky under full-suite parallel load (failed once, passed on immediate re-run and isolation); logic unchanged by this slice (path prefix only). (5) `entityContext.js` and V5 view links now emit `/legacy/...` paths so cross-links stay inside the legacy shell when opened from V5 surfaces.

**Pass 5 — Verification reproduction:** PASS
- Commands run: `cd ui && npm test -- next` (twice; first run hit one flake in ReviewSurface duration test, second run 44/44 green); `bash scripts/v6_check_review_verdict.sh v6-60-promote-shell` (after writing this file).
- Result: UI — 10 files, 44 tests passed. Verdict script exits 0.

**Fixes applied in this review:** none

**Required changes before merge:** none

**Optional suggestions (non-blocking):**
- Stabilize `ReviewSurface` "sends review duration when a report leaves the queue" test (fake timers / explicit flush) — intermittent under full `next` suite load.
- Add a smoke test that bare `/next` (no trailing path) redirects to `/today` via `/`.
- V6-63 docs slice should update `README.md` / `AGENTS.md` to describe `/` as v6 default (DEPLOY.md already updated).
