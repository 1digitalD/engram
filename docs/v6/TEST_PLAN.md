# Engram v6 — Test Plan: Use Cases, Test Cases, Edge Cases, Metrics

Companion to `docs/v6/SOLUTION_DESIGN.md` and `IMPLEMENTATION_PLAN.md`.
Layers: pytest unit (`tests/unit/`), pytest integration (`tests/integration/`,
test DB :5433 only), Vitest component (`ui/`), replay eval
(`scripts/replay_eval.py`), and manual E2E passes tied to use cases.

---

## 1. Primary use cases

Each UC is a manual E2E script run at its phase's deploy gate and re-run at
Phase 6 cutover.

**UC-1 — Paste a multi-topic meeting transcript (Phase 1, flagship).**
Paste a 45-min transcript covering 2 Spaces + 1 unknown topic into capture.
Expect: exactly one report; sections ordered (routing summary → applied
annotations → proposed commitments → decisions → questions → leftovers);
every item carries a receipt (tap → highlighted transcript lines); ambiguous
speakers produce attribution *questions*, not guessed owners; batch-accept
of remainder in one tap; whole review lands as one undoable ChangeBatch.
Pass bar: review completed < 90s without opening the raw transcript.

**UC-2 — Cold-start on an initiative after two weeks away (Phase 3).**
Open a Space Dossier. Expect: Brief current (or staleness labeled), Spine
shows the story, open commitments with ages, decisions with dates, reading
time ≤ 1 min to "I know where this stands."

**UC-3 — Portfolio scan (Phase 2).**
Open Workboard. Expect: every open commitment across all Spaces; state chip
counts match reality; group-by-person answers "what is X carrying?"; every
at-risk flag shows a one-line reason that survives a "is that fair?" check.

**UC-4 — Correct a wrong extraction (Phase 3).**
A commitment was routed to the wrong Space with the wrong owner. Move it and
fix the owner inline (2 gestures). Expect: both changes are Ledger events;
both fields now pinned; a later transcript contradicting them produces
*proposals*, never silent overwrites.

**UC-5 — Hands-on work item management (Phase 3).**
On the Dossier: add a commitment inline, log an update, mark another done.
Expect: three one-line interactions, three human-authored Ledger events, no
form at any point.

**UC-6 — Morning triage (Phase 4).**
Open Today. Expect: needs-you vs. in-motion split; fired markers and ripened
follow-ups present with receipts; newly-at-risk since yesterday listed;
nothing requiring a hunt through other surfaces.

**UC-7 — Nudge a silent waiting-on (Phase 4).**
A waiting-on ripens. Expect: drafted nudge citing the original ask and date;
edit + copy; "nudged" logged; reply pasted later reconciles onto the same
commitment (via normal capture flow).

**UC-8 — Meeting prep (Phase 4).**
"Prep me for Maria." Expect: she-owes/you-owe, shared open decisions,
discuss-markers filed for her, changes since last met — all cited.

**UC-9 — Weekly digest (Phase 5).**
Friday: open Review's digest. Expect: moved/decided/stalled/next, cited,
editable, copy-out as a status update without rewriting.

**UC-10 — Monthly health (Phase 5).**
Open monthly briefing. Expect: quiet people / at-risk Spaces / idle themes /
unowned work — only sections with content; every claim cited.

**UC-11 — Theme lifecycle (Phase 5).**
Name a theme, attach two decisions and a question over a week, promote to
Space. Expect: history, links, decisions all present on the new Space; a
`promoted` event in its Ledger.

**UC-12 — Agent hygiene via MCP (Phases 1, 6).**
An agent calls `capture` then `submit_candidates`. Expect: results land in
reports (never auto-created entities); `agent:*` attribution throughout;
`resolve_report` works end-to-end from the MCP client.

## 2. Test-case matrix by feature

Naming: TC-<phase><n>. Representative, not exhaustive — slices add cases.

### Phase 0
- TC-01 route-table parity before/after package split (generated fixture diff).
- TC-02 full suite green post-split with zero test edits (mechanical proof).
- TC-03 operator setting: get/put, backfill, missing-operator → derived
  states degrade gracefully (everything `mine`), API flags unconfigured.

### Phase 1 — reports (unit: assembler; integration: endpoints)
- TC-10 grouping: N candidates from one capture → one report, all
  `report_id` set, queue endpoint shows one item.
- TC-11 sectioning: candidate types map to correct sections in stable order.
- TC-12 attribution: speaker-less commitment candidate → question item with
  `owner=null`, never a guessed owner (assert against fixture transcripts).
- TC-13 annotate lines: auto-applied tag/link appears in report as
  undoable line referencing its `EntityEvent`.
- TC-14 resolve atomicity: mixed accept/edit/dismiss + `accept_rest` → one
  `ChangeBatch`; mid-apply failure rolls back everything (inject failure).
- TC-15 undo review: revert the ChangeBatch → all applied items reverted,
  report returns to `pending`, dismissals *retained* in dismissal memory.
- TC-16 `later`: report `partial`; remaining items resolvable later; report
  `reviewed` only when none pending.
- TC-17 re-distill: prior report `superseded`; unresolved suggestions from
  it expire; resolved ones untouched.
- TC-18 auto-create retired: 0.95-confidence create candidate → proposal,
  no entity row, no `agent:*` create event.
- TC-19 MCP: `capture` returns `report_id`; `resolve_report` round-trip.

### Phase 2 — workboard
- TC-20 each state predicate (mine/waiting-on/overdue/stale/blocked/at-risk)
  against a seeded portfolio fixture; counts match chip counts.
- TC-21 group pivots return identical item sets, different grouping.
- TC-22 at-risk reasons: every flag has non-empty `reason` + receipt refs.
- TC-23 hysteresis: entity crossing threshold then improving by <2d stays
  flagged; ≥2d clears.
- TC-24 per-Space threshold override changes staleness verdicts.

### Phase 3 — pinning + manipulation
- TC-30 matrix test: field × actor (user, agent, MCP on_behalf) × pin-state
  → write / pin / demote-to-propose as specified (parameterized).
- TC-31 accept-proposal-on-pinned-field updates value, keeps pin.
- TC-32 unpin endpoint → next AI annotate write succeeds again.
- TC-33 move-to-Space: old parent link removed, new one created, single
  gesture = single ChangeBatch, events on both.
- TC-34 amend update: content changed, `EntityEvent` has old+new, Dossier
  renders amended-with-history.
- TC-35 archive vs delete: archive reversible + excluded from Workboard;
  delete writes tombstone event; children/links handled per FK rules.
- TC-36 redact note: content tombstoned, chunks gone (no vector hits),
  citing items render redacted state, event contains no old content.

### Phase 4 — markers/today/nudge
- TC-40 marker firing: due nudge marker → Today feed once (`fired_at` set),
  not duplicated on later runs.
- TC-41 discuss marker → appears in prep for its person, not in Today.
- TC-42 marker on archived/done entity → auto-resolved, never fires (EC-15).
- TC-43 newly-at-risk diff: snapshot job; item at-risk in yesterday's
  snapshot doesn't reappear as "new."
- TC-44 nudge draft contains the original ask, date, and receipts; drafts
  are never auto-sent anywhere.

### Phase 5 — themes/insights
- TC-50 theme type accepted by constraint; excluded from Workboard commit
  states; shown on Themes rail with idle detection.
- TC-51 promote: type flips theme→project, links/tags/events/decisions
  intact, `promoted` event written; promote on non-theme → 4xx.
- TC-52 `/convert` removed → 404/410; MCP contract updated.
- TC-53 monthly briefing: each signal computed from seeded fixture; empty
  sections omitted; fully-empty briefing returns explicit "nothing to say".

### Phase 6 — cutover
- TC-60 route `/` serves new shell; `/legacy` serves old (week window only).
- TC-61 post-deletion: build green, no imports of removed modules, bundle
  size drop recorded.
- TC-62 MCP smoke of all new tools against deployed instance.

## 3. Edge-case catalog

Extraction/report (Phase 1):
- EC-01 empty or whitespace capture → no report, friendly no-op.
- EC-02 huge transcript (> chunking limit) → single report still; sections
  merged across chunks; no duplicate candidates from chunk overlap.
- EC-03 same commitment stated twice in one transcript → one candidate.
- EC-04 commitment already existing and *already done* mentioned again →
  update/annotation on the done item or question — never a duplicate create.
- EC-05 contradictory dates within one transcript ("Friday… actually
  Monday") → latest wins in the proposal, both cited.
- EC-06 transcript mentioning a dismissed-before suggestion → suppressed via
  dismissal memory, visible under leftovers ("set aside as noise before").
- EC-07 capture while a prior report for the same Space is still pending →
  both reports independent; accepting older one after newer doesn't
  resurrect stale values over newer ones (apply checks current state).
- EC-08 person name collision (two Marias) → attribution question with
  candidate list, not a guess.
- EC-09 LLM/extraction failure mid-pipeline → capture preserved (note safe),
  job retries per `Job` policy, report `pending` with error surfaced;
  never a half-written report visible as complete.

Workboard (Phase 2):
- EC-10 task with no due date and no Space activity → stale applies,
  overdue never does.
- EC-11 Space with finish line but zero commitments → at-risk only via
  quiet-Spine rule; no divide-by-zero on the % rule.
- EC-12 blocked chain A→B→C resolved at the head → all downstream unblock
  on next query (no cached staleness).
- EC-13 operator unset → Workboard renders without mine/waiting-on split +
  setup prompt.
- EC-14 archived Space with open tasks → excluded from Workboard, but tasks
  surface in monthly "unowned/orphaned" signal.

Markers/Today (Phase 4):
- EC-15 marker due on an entity archived/done before firing → auto-resolved.
- EC-16 marker with date in the past at creation → fires on next cycle, once.
- EC-17 two markers same entity same day → both fire as separate lines.
- EC-18 timezone: marker set "Friday" fires Friday local (operator TZ
  setting), not UTC-shifted Thursday.

Manipulation/pinning (Phase 3):
- EC-20 concurrent MCP write during human resolve → last-writer wins per
  field but both events recorded; pinned fields still reject the agent.
- EC-21 undo a review batch after a later manual edit to one item → batch
  revert skips the conflicted field, reports partial revert honestly.
- EC-22 redact a note cited by an *accepted* commitment → commitment keeps
  its data; receipt renders redacted; no cascade delete.
- EC-23 delete a person owning open tasks → blocked with guidance (reassign
  or archive first); FK `SET NULL`/`CASCADE` behavior asserted.

Themes (Phase 5):
- EC-24 promote a theme whose name collides with an existing Space →
  conflict prompt (merge-into vs rename), no silent dedupe.
- EC-25 demote/re-promote round trip is not supported → promote is one-way;
  API rejects project→theme.

## 4. Quality gates in CI order

Per slice: focused pytest → full backend suite (serial, :5433) → `cd ui &&
npm test && npm run build`. Per phase: replay eval where extraction was
touched, deploy-gate checklist from IMPLEMENTATION_PLAN, `backup_prod.sh`
before deploy.

## 5. Product metrics (the numbers that decide Phase 1's gate)

Recorded in `metrics/trust` + replay results; baseline row filled at V6-14.

| Metric | Source | Baseline (fill in) | Target |
|---|---|---|---|
| Median review time per pasted transcript | client instrumentation | 0 completed reviews / no median yet (2026-07-07 baseline) | < 90s (stretch 60s) |
| Report items accepted without edit | resolve payloads | — | ≥ 70% |
| Corrections after acceptance (re-home/owner/date fixes within 7d) | Ledger events | — | ≤ 10% of accepted items |
| Auto-created entities | events | (current: >0) | 0 |
| Replay eval extraction precision / recall | `scripts/replay_eval.py` | grouping 1.000, sectioning 1.000 across 11 fixture-backed reports (`--dry-run`, 2026-07-07) | no regression; grouping score added |
| At-risk flags active at once | workboard | — | ≤ 5, all judged legitimate in weekly check |
| Suggestion queue leakage (suggestions with no `report_id`) | SQL | — | 0 after Phase 1 |
