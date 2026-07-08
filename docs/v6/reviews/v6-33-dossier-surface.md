## Review: v6-33-dossier-surface

**Verdict:** APPROVE

Reviewed commit: 979a0ce1 (`v6-33-dossier-surface: Dossier surface in /next`), 11 files, +1234/−5.

**Pass 1 — Spec conformance:** PASS
- Notes: all four acceptance criteria are satisfied.
  - Dossier loads Brief + Spine for a Space entity: `DossierSurface` parallel-fetches `entities.detail(spaceId)`, `brief()`, and `timeline({ thread_id: spaceId, limit: 40 })` (DossierSurface.jsx:88-91). Client-side `buildSpaceBrief` scopes portfolio brief items to the Space and its open tasks, with entity AI summary fallback and staleness chip via `briefStalenessLabel`. Spine renders timeline narrations with actor labels and glyphs.
  - Open commitments, decisions, questions sections render: commitments come from `openCommitmentsFromDetail` partitioned into Yours / Waiting on others; decisions from `decisions.list({ thread_id: spaceId })`; questions from pending suggestions filtered by `openQuestionsFromSuggestions`. All three sections have empty states and are covered by `DossierSurface.test.jsx`.
  - Ledger tab shows attributed timeline with amend history: Overview/Ledger tab switch loads `entities.events(spaceId)`; ledger rows show actor, timestamp, event type, narration, reason, and `eventAmendDetail` old→new lines for amended updates (TC-34 dossier rendering path).
  - Component tests cover Brief/Spine/Ledger tabs: five Vitest cases assert brief narrative + spine events, decisions/commitments/questions, ledger amend detail, pin toggle, and Spaces→Dossier navigation.
- Route wiring matches task description: `/next/spaces/:spaceId` in NextApp.jsx; Spaces nav enabled in NextShell.jsx; Workboard bucket titles link to dossier when `bucket.kind === 'space'`. Pin/unpin affordances on header fields call `v4API.entities.pin/unpin`. UC-2 remains a manual deploy-gate pass per IMPLEMENTATION_PLAN — not in this slice's automated acceptance criteria. No out-of-scope backend changes; no criterion weakened.

**Pass 2 — PREAMBLE conformance:** PASS
- Notes: implementation is slice-shaped — new DossierSurface + dossierUtils + SpacesSurface, shared CSS module, focused tests, minimal shell/client wiring (pin/unpin client methods, nav enable, Workboard link). Pure helpers live in `dossierUtils.js`; UI reuses v6-31 `TypedAffordances` for inline manipulation without new abstraction layers. No TODOs, commented-out code, or swallowed exceptions (load/action errors surface via `friendlyApiError` + `role="alert"`). Reuses `v5ThreadDetailUtils` read-only helpers rather than duplicating section parsing — import-only, not extending legacy views.

**Pass 3 — Skill conformance (tdd / incremental-implementation):** PASS
- Notes: single logical commit with tests and implementation together; test names describe behavior (`loads brief and spine for a space entity`, `shows ledger tab with attributed timeline and amend history`, `toggles pin state from the dossier header`). Existing NextApp/Workboard tests preserved; mock surface extended for new client methods. Commit message references task id (v6-33). Matches incremental-implementation one-slice discipline.

**Pass 4 — Adversarial read:** PASS
- Findings (all verified non-blocking):
  - Brief scoping is client-side: `GET /brief` returns portfolio-wide data (existing v4 contract); `buildSpaceBrief` filters items to Space + open task ids and falls back to entity AI summary. Staleness is labeled on the header chip. Acceptable given current brief service; no incorrect data shown.
  - Questions fetch all pending suggestions then filter locally — fine for single-user scale; could add server-side thread filter later if suggestion volume grows.
  - `eventAmendDetail` renders old→new for any `updated` event with values, including pin events — shows field diffs in Ledger, not just `reason=amended`; consistent with "attributed timeline" and harmless.
  - `handleAddCommitment` creates task then links; link failure leaves orphan task (same pattern as v6-31 Workboard — task visible, re-linkable).
  - Pin toggle and affordance handlers only reachable after entity load; no race on null entity id.
  - Invalid dates degrade to empty strings in formatters; no throw paths found.
  - Parallel `Promise.all` load: one failure clears detail and shows error — no partial stale state beyond cleared detail.

**Pass 5 — Verification reproduction:** PASS
- Commands run:
  - `cd ui && npm test -- next` (main repo at commit 979a0ce1 lineage): 7 files, 31 tests passed including `DossierSurface.test.jsx` (5 tests).
  - `cd ui && npm test -- DossierSurface` (worktree): 5 dossier tests passed.
  - `bash scripts/v6_check_review_verdict.sh v6-33-dossier-surface`: OK (Verdict APPROVE, Passes 1–5 PASS).
- Result: UI tests green on reviewed tree. `ReviewSurface > sends review duration report when report leaves queue` flakes intermittently in the codloop worktree (timing-sensitive `Date.now` mock); passes reliably on main repo and is unrelated to dossier changes. Orchestrator validation evidence on commit 979a0ce1 also recorded 31 UI tests passed, `npm run build` OK, and 593 backend tests via `v6_validate_slice.sh`.

**Fixes applied in this review:** none

**Required changes before merge:** none

**Optional suggestions (non-blocking):**
- Pass `thread_id` to `GET /brief` if the brief service gains Space-scoped generation — would reduce payload and make scoping server-authoritative.
- Add a Vitest case asserting the brief staleness chip text (`as of …`) when `generated_at` is present.
- Filter suggestions API call with a thread/space query param when the backend supports it, to avoid loading all pending suggestions on every dossier open.
