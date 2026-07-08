## Review: v6-13-next-review-ui

**Verdict:** APPROVE

**Pass 1 — Spec conformance:** PASS
- `ui/src/next/` shell mounted at `/next` via additive `App.jsx` route.
- Chrome: capture field, omni-bar nav, review pulse count (`NextShell.jsx`).
- Review surface loads reports from `v4API` reports endpoints; per-item verify/edit/dismiss/later + accept-rest wired (`ReviewSurface.jsx`).
- `vocab.js` maps v4 DTO terms to vision labels (sections, entity types, surfaces).
- Vitest: `ReviewSurface.test.jsx` (8), `vocab.test.js` (5) — 16 tests pass.
- `npm run build` green.

**Pass 2 — PREAMBLE conformance:** PASS
- New files under `ui/src/next/` only; one additive route line in `App.jsx`.
- `v4Client.js` extended additively for reports API.
- No changes to `ui/src/views/` or `ui/src/lab/`.

**Pass 3 — Skill conformance (TDD / incremental):** PASS
- Component tests cover report rendering and action wiring.
- Vocabulary module tested separately.

**Pass 4 — Adversarial read:** PASS
- API errors surfaced via `friendlyApiError`.
- Non-resolvable (applied) items shown distinctly with undo deferred note.
- Dismiss reasons from `reviewUtils` constants.

**Pass 5 — Verification reproduction:** PASS
- `cd ui && npm test -- next` — 16 passed
- `cd ui && npm run build` — green

**Fixes applied in this review:** Overseer takeover after Loopsmith merge_conflict on cursor attempt a063 (product code unchanged).

**Required changes before merge:** None.

**Optional suggestions (non-blocking):**
- Receipt tap-to-highlight transcript lines (UC-1) may need follow-up once capture report narrative stabilizes.

**Reviewer:** overseer (Loopsmith takeover, 2026-07-08)
