# Engram v6 — Implementation Plan

Status: **active plan** (2026-07-07). Design: `docs/v6/SOLUTION_DESIGN.md`.
Tests/metrics: `docs/v6/TEST_PLAN.md`. Process rules: `AGENTS.md`,
`docs/V4_PRINCIPLES.md` (production data safety is unchanged and binding).

Delivery model is unchanged: slice-by-slice, each slice scoped → tested →
committed → reviewed before the next. Slices are sized for one worktree run
(Loopsmith drain or direct sub-agent). Deploy gates are per phase, each with
`bash scripts/backup_prod.sh` first and smoke via `scripts/engram-deploy.sh`.

**Phase order is deliberate**: distillation quality (Phase 1) is the
load-bearing bet and gets measured before further surfaces are built.
Workboard (Phase 2) is the cheapest high-value win. Nothing in Phases 2–5
depends on Phase 1's *quality*, but building six surfaces over a noisy
distiller would repeat the v4→v5 mistake — hence the Phase 1 gate.

---

## Phase 0 — Foundations (no behavior change)

| Slice | Scope | Acceptance |
|---|---|---|
| V6-00 Archive & docs | Move superseded plans/iterations/PRDs to archives; write v6 docs; slim tracker; update AGENTS/README | Done in the same change series as this plan |
| V6-01 API package split | `api/v4_entities.py` → `api/v4/` package per DESIGN §8.1; no route, shape, or behavior change | Full backend suite passes unchanged (~505); route table diff is empty (`flask routes` before/after) |
| V6-02 Operator identity | `operator_person_id` in `AppSetting` + `GET/PUT /settings/operator`; backfill from existing owner settings if present | Unit + integration tests; UI unaffected |

Deploy gate 0: backend suite green, `npm run build` green, deploy, smoke.
No migrations in this phase.

## Phase 1 — Distillation report + trust policy (the flagship)

Migrations: `NNN_distillation_reports.sql` (reports table + `report_id` on
`ai_suggestions`).

| Slice | Scope | Acceptance |
|---|---|---|
| V6-10 Report assembler | `services/v4_report.py`: group/order candidates into report sections incl. attribution questions; job-worker integration; supersede-on-redistill | Unit tests over section ordering, grouping, attribution-question emission (TEST_PLAN TC-1x) |
| V6-11 Resolve endpoint | `GET /reports*`, `POST /reports/<id>/resolve` applying one `ChangeBatch`; `later`/`partial`; dismissal-memory wiring | Integration tests incl. atomicity + undo of a whole review |
| V6-12 Retire auto-create | Delete threshold auto-create path; creation candidates always land in reports; annotate-tier items appear as undoable report lines | No `agent:*` entity-creation events on new captures; replay eval re-run |
| V6-13 New shell + Review surface | `ui/src/next/` shell at `/next`: chrome (capture, omni-bar, pulse), Review surface rendering reports with per-item verify/edit/dismiss + accept-rest | Vitest component tests; manual E2E per TEST_PLAN UC-1 |
| V6-14 Eval + metrics | Extend `scripts/replay_eval.py` to score report grouping/sectioning; client review-time instrumentation into `metrics/trust` | Baseline numbers recorded in TEST_PLAN §5 table |

**Deploy gate 1 (measured):** two weeks of real use after deploy —
median review time per pasted transcript < 90s (target 60s), report
acceptance-without-edit ≥ 70%, zero auto-created entities. If the gate
fails, iterate on extraction/assembly *before starting Phase 2 UI work*
(at most: V6-20 backend may proceed in parallel).

## Phase 2 — Workboard

No migrations (derived states are query-time).

| Slice | Scope | Acceptance |
|---|---|---|
| V6-20 Derived states + endpoint | `GET /workboard` per DESIGN §10.1: states, groupings, at-risk v1 with reasons + hysteresis; per-Space thresholds in `properties.thresholds` | Unit tests over every state predicate + edge cases EC-10..14 |
| V6-21 Workboard surface | Screen per mockup 07: filter chips with counts, group toggle, inline actions (done, nudge-draft placeholder, marker placeholder), Themes rail placeholder | Component tests; UC-3 manual pass |
| V6-22 Stream surface | Chronological capture log (cheap: notes list + day grouping + type glyphs) | Component tests |

Deploy gate 2: suites green, deploy, smoke; at-risk flags eyeballed against
the real portfolio for one week (expect ≤5 flags; all must feel legitimate —
this is UX_VISION §9.7's calibration pass).

## Phase 3 — Dossier + direct manipulation + pinning

Migrations: `NNN_pinned_fields.sql`, `NNN_redacted_lifecycle.sql`.

| Slice | Scope | Acceptance |
|---|---|---|
| V6-30 Pin enforcement | `services/v4_trust.check_pin`; human writes pin; AI writes to pinned fields demote to propose; explicit pin/unpin endpoints | Property-style tests over field × actor × pin-state matrix (TC-3x) |
| V6-31 Typed affordances | Inline status/due chips, move-to-Space, hand-to-owner, attach-entry, fast paths (add commitment, log update, mark done) — all writing events | Component + integration tests; UC-4, UC-5 |
| V6-32 Amend/archive/redact/delete | Update amendment with old→new in Ledger; archive default; delete tombstone; note redaction with visible citation breakage | Integration tests EC-20..23 |
| V6-33 Dossier surface | Brief (existing service) + Spine + open commitments + decisions + questions + Ledger tab | Component tests; UC-2 manual pass |

Deploy gate 3: suites green, deploy, smoke. Verify pin behavior against a
live re-distillation (paste a transcript contradicting a pinned date → must
propose, not overwrite).

## Phase 4 — Today + markers + nudge drafting

Migrations: `NNN_followup_markers.sql`.

| Slice | Scope | Acceptance |
|---|---|---|
| V6-40 Markers backend | CRUD + firing job (due markers → Today feed; discuss markers → prep payloads) | Unit + integration; EC-15..17 |
| V6-41 Today surface | Needs-you vs. in-motion split; fired markers; ripened follow-ups; newly-at-risk diff (daily snapshot job) | Component tests; UC-6 |
| V6-42 Nudge drafting | `POST /commitments/<id>/nudge-draft` from receipts; draft-only UX (copy button) | Prompt fixture tests; UC-7 |
| V6-43 Meeting prep | "Prep me for X" via existing ask/prep machinery + discuss markers + mutual commitments | Integration tests; UC-8 |

Deploy gate 4: suites green, deploy, smoke.

## Phase 5 — Themes + insight horizons

Migrations: `NNN_theme_type.sql`.

| Slice | Scope | Acceptance |
|---|---|---|
| V6-50 Themes | `theme` type; create from omni-bar; attach decisions/questions; `promote` (theme→project, events + links preserved); retire `/convert` | Integration tests; EC-24..25 |
| V6-51 Weekly digest | Package `/summary` + brief into Review's weekly digest (cited, editable, copy-out) | Component tests; UC-9 |
| V6-52 Monthly health | `/insights/monthly` briefing + Workboard placement; empty-section omission | Unit tests over each signal; UC-10 |
| V6-53 People surface | Person page: owes/owed, quiet detection, prep shortcut (largely existing rollup data) | Component tests |

Deploy gate 5: suites green, deploy, smoke.

## Phase 6 — Cutover and demolition

| Slice | Scope | Acceptance |
|---|---|---|
| V6-60 Promote shell | `/next` becomes `/`; current V5+lab shell extracted to `ui/src/legacy/` and mounted at `/legacy/*` as the **runtime fallback** | Manual side-by-side week; no data divergence (same API); `/legacy` remains until explicit removal |
| V6-61 Delete legacy UI | **Deferred** until overseer sign-off after cutover validation. Tag `engram/v6-phase-5-complete` is the deploy rollback point. When removed: delete `ui/src/legacy/*`, legacy routes, and their tests | Build green; no dangling imports |
| V6-62 MCP alignment | Add `list_reports`/`get_report`/`resolve_report`/`get_workboard`/`add_marker`/`draft_nudge`; `capture` returns `report_id`; README_V4 contract update | MCP unit tests; live smoke via MCP client |
| V6-63 Docs & tracker | README, AGENTS.md, tracker reflect v6 as the only UI; UX_VISION marked "implemented baseline" with deviations noted | Docs review |

Deploy gate 6 (final): full suites, build, backup, deploy, smoke, and the
TEST_PLAN §5 metrics re-run recorded in the tracker.

---

## Standing constraints (every phase)

- Additive-only migrations; numbered scripts; test DB (5433) first, prod
  (5432) only after `backup_prod.sh`. Never `init-db` on prod.
- Backend pytest serial against the shared test DB.
- Meaningful mutations write `entity_events`; AI actors are `agent:*`.
- New routes go in the owning `api/v4/` module — the monolith must not regrow.
- Each slice updates `EXECUTION-TRACKER.md` (status only; history stays in
  `docs/archive/EXECUTION-TRACKER-v4-history.md`).

## Explicitly out of scope (do not build without a new decision)

Agent runs / Pulse run cards; NL standing orders; nudge sending
(email/Slack); calendar/recorder ingestion; plan-slip history; multi-user;
graph views; recurring tasks. See UX_VISION §10.
