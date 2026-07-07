# Engram v6 — Solution Design

Status: **approved baseline** (2026-07-07)
Authority: `docs/ux-vision/UX_VISION.md` (the *what* and *why*; §10 records the
adopted build stance). This document is the *how*. Where they conflict, fix the
conflict — don't silently pick one.

Companions: `docs/v6/IMPLEMENTATION_PLAN.md` (sequencing),
`docs/v6/TEST_PLAN.md` (use cases, test cases, edge cases, metrics).

## 1. What v6 is

v6 is the product layer that implements the UX vision on top of the existing
v4 backend. It is **not** a new runtime version: the API stays `/api/v4`, the
schema evolves additive-only, production data is preserved throughout.

Why "v6" and not "v5": the v5 label is burnt — `ui/src/views/V5*.jsx` and the
"V5 Productivity/Hardening" iterations already use it for the UI generation v6
replaces. Reusing it would guarantee confusion.

Scope guardrails (from UX_VISION §1 and §10):

- **One operator.** Teammates appear as People entities; they never log in.
- **Pasted input.** Transcripts arrive by hand; no recorder/calendar/webhook
  integrations.
- **Deferred entirely**: agent runs / Pulse run cards, natural-language
  standing orders (per-Space threshold *settings* ship instead), nudge
  *sending* channels (drafts only — the operator copies/sends), plan-slip
  history, multi-user.

## 2. Architecture at a glance

Unchanged substrate:

- Flask + SQLAlchemy, Postgres + pgvector, background `Job` worker.
- `Entity` single-table model, `EntityLink` relationships, `EntityEvent` +
  `ChangeBatch` audit, `AiSuggestion` proposals, `Decision`, hybrid search,
  embeddings, `v4_brief`/`v4_ask`/`v4_attention` services.
- MCP server as a thin proxy over `/api/v4`.

What v6 adds or changes:

| Layer | Change |
|---|---|
| Schema | 5 additive migrations (§5) |
| Extraction output | One **distillation report** per capture replaces the loose suggestion queue (§6) |
| Trust policy | Auto-create at ≥0.9 retired; creation is always propose-tier; **human edits pin** (§7) |
| API | New endpoints for reports, workboard, markers, insights; `api/v4_entities.py` split into a package (§8) |
| UI | New app shell built clean at `/next`, promoted to default at parity; legacy strata deleted (§9) |
| Derived signals | Workboard states, at-risk flags with reasons, three insight horizons (§10) |
| MCP | New tools mirroring reports/workboard/markers (§11) |

## 3. Domain vocabulary

v6 renames live in **UI vocabulary and DTO field names only**. The database
keeps v4 names (additive-only rule). One mapping module in the UI
(`ui/src/next/vocab.js`) and one DTO layer serverside own the translation —
nothing else may hardcode the mapping.

| UX vision term | v4 storage | Notes |
|---|---|---|
| Stream entry | `note` entity | immutable source artifact; redaction only (§5.5) |
| Space | `project` (and `area` as parent context) | UI presents both as Spaces; `project parent area` links unchanged |
| Theme | `theme` entity (new type value) | lightest container; promotable to project (§5.4) |
| Commitment | `task` + `assigned_to` link | owner, `due_at`, status |
| Waiting-on | `task` whose owner ≠ operator | derived, not a type |
| Finish line | `due_at` on a project | |
| Decision | `Decision` row | unchanged |
| Ledger | `EntityEvent` + `ChangeBatch` | unified read view, no new store |
| Proposal | `AiSuggestion` | gains `report_id` (§5.1) |
| Receipt | `source_note_id` + `evidence` | unchanged |
| Follow-up marker | `followup_markers` row (new) | §5.3 |
| Brief / Spine | `v4_brief` output / entity timeline | existing services |

## 4. The operator identity

Derived states (waiting-on vs. mine) require knowing which `person` entity is
the operator. This already exists via owner settings (`/entities/<id>/owner`);
v6 treats it as required configuration: the app prompts once on first run of
the new shell and stores it in `AppSetting` (`operator_person_id`).

## 5. Schema changes (all additive, numbered scripts in `scripts/migrations/`)

### 5.1 `distillation_reports` + `ai_suggestions.report_id`

```sql
CREATE TABLE distillation_reports (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  source_note_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending',    -- pending|reviewed|partial|superseded
  narrative JSONB NOT NULL DEFAULT '{}',      -- ordered sections, see §6
  stats JSONB NOT NULL DEFAULT '{}',          -- counts per section, timings
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  reviewed_at TIMESTAMP
);
ALTER TABLE ai_suggestions ADD COLUMN report_id TEXT
  REFERENCES distillation_reports(id) ON DELETE SET NULL;
```

One report per capture. Re-distilling the same note supersedes the prior
report (`status='superseded'`) rather than mutating it.

### 5.2 `entities.pinned_fields`

```sql
ALTER TABLE entities ADD COLUMN pinned_fields JSONB NOT NULL DEFAULT '[]';
```

A list of objects `{"field": "due_at", "pinned_at": ..., "event_id": ...}`.
Pinnable: `status`, `due_at`, `title`, `owner` (the assigned_to link), and
`parent` (the parent link). A field is pinned by any human-authored write to
it (§7.3). Unpinning is an explicit action ("let AI manage this again"),
also an event.

### 5.3 `followup_markers`

```sql
CREATE TABLE followup_markers (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('nudge','discuss','custom')),
  due_at TIMESTAMP,                -- nudge: fires into Today on this date
  person_entity_id TEXT REFERENCES entities(id) ON DELETE SET NULL,
                                   -- discuss: rides into prep for this person
  note TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  fired_at TIMESTAMP,
  resolved_at TIMESTAMP
);
```

Multiple markers per entity are allowed. `entities.follow_up_at` remains for
the *passive* ripening path; markers are the explicit path. Both feed the
same Today queue.

### 5.4 `theme` entity type

Extend `chk_entities_type` with `'theme'` (drop/recreate constraint with the
superset — additive enum value per V4_PRINCIPLES). Promotion theme→project is
a **restricted type conversion**: allowed only for `theme→project`, writes an
`EntityEvent` (`event_type='promoted'`), preserves all links, tags, events,
and attached decisions/questions. The general `/convert` endpoint is retired
(§8) — promotion is its only surviving, purpose-built descendant.

### 5.5 `redacted` lifecycle

Extend `chk_entities_lifecycle` with `'redacted'`. Redacting a note (the only
type it applies to): content and title are replaced with a tombstone string,
`entity_chunks` rows are deleted (removes embeddings), the event records that
a redaction happened but **not** the old content. Anything citing the note
renders "cites a redacted entry" — visibly broken, never silently orphaned.

## 6. Distillation pipeline v2 — one capture, one report

Current pipeline (kept): capture → `v4_extraction` produces candidates →
`v4_reconciliation` matches against the Fabric (semantic dedup, fingerprints,
dismissal memory). All of that machinery is reused.

What changes is the **output contract**. Instead of writing N independent
`AiSuggestion` rows into a queue, a new **report assembler**
(`services/v4_report.py`, runs in the job worker after reconciliation):

1. Groups all candidates from one capture under one `distillation_reports`
   row (suggestions get `report_id`).
2. Orders them into sections mirroring UX_VISION §3: **routing summary** →
   **updates to existing work** (annotate-tier, pre-applied, undoable) →
   **new commitments** (propose) → **decisions** (propose) → **open
   questions**, including *attribution questions* ("who committed to this?")
   when speaker labels are missing/ambiguous — the assembler asks instead of
   guessing an owner → **leftovers** (unrouted lines, kept as stream-only).
3. Writes the narrative (section order, per-item one-line reasons, receipts
   as note offsets) into `narrative` JSONB.

Review protocol (`POST /api/v4/reports/<id>/resolve`):

- Body: `{decisions: [{suggestion_id, action: accept|edit|dismiss|later,
  edits?, dismissal_reason?}], accept_rest: bool}`.
- Applied atomically as **one `ChangeBatch`** — the whole review is one
  undoable unit, matching the existing undo machinery.
- `later` leaves items pending and marks the report `partial`.
- Dismissals feed the existing semantic dismissal memory unchanged.

Annotate-tier items (tags, links to existing entities, summaries) are applied
at distillation time as today — but they appear *in the report* as "already
done, tap to undo" lines, not as silent side effects. **Exception:** an
annotate-tier write that touches a pinned field is demoted to propose (§7.3).

## 7. Trust policy

### 7.1 Retire auto-create

`AUTO_CREATE_THRESHOLD` logic is removed, not set to 1.0 — dead code is
deleted (Principle: entity creation is consequential ⇒ consented). Existing
`agent:*` auto-create audit paths remain for history display. This ships in
the **same phase** as the report UI: batch-accept is what keeps review cost
tolerable once nothing auto-creates.

### 7.2 The three verbs

| Verb | v4 mechanism | Examples |
|---|---|---|
| Annotate (act + undoable) | direct write + `EntityEvent`, shown in report | tags, links to existing, summaries, brief refresh |
| Propose (ask first) | `AiSuggestion` in a report | create anything, status change, owner change, due change, merge, close, delete |
| Pinned-field exception | propose even if otherwise annotate | any write to a pinned field |

### 7.3 Human edits pin

Enforcement point: a single helper in the write path
(`services/v4_trust.py: check_pin(entity, field, actor)`) consulted by
reconciliation and by suggestion-apply. Rules:

- Any successful human-authored write (`actor='user'` or MCP acting for the
  operator with `on_behalf=user`) to a pinnable field adds it to
  `pinned_fields`.
- AI writes to a pinned field are converted into proposals with the pin
  surfaced in the reason ("you set this to Friday on Jul 3; Thursday's
  transcript suggests Monday").
- Accepting such a proposal updates the value and **keeps the pin** (the
  human decided again). Explicit unpin is a separate affordance.

### 7.4 Direct manipulation (UX_VISION §5)

All typed affordances ride existing endpoints — `PATCH /entities/<id>`
(status, dates, title), links endpoints (re-home, attach), owner endpoints —
which already write events. v6 adds: amend-with-history for activity updates
(PATCH on the update note; `EntityEvent` already stores old/new), archive as
the default destructive verb, delete-with-tombstone, note redaction (§5.5).

## 8. API changes

### 8.1 Split `api/v4_entities.py` (7.6k lines) into a package

```
api/v4/__init__.py        # blueprint assembly; URL prefix unchanged
api/v4/capture.py         # /capture
api/v4/reports.py         # /reports, /reports/<id>, /reports/<id>/resolve
api/v4/entities.py        # entity CRUD-adjacent routes, events, merge
api/v4/links.py           # relationships, owner
api/v4/workboard.py       # /workboard
api/v4/today.py           # /today, /today/review, markers feed
api/v4/markers.py         # /markers CRUD
api/v4/recall.py          # /search, /ask, /entities/mentions
api/v4/insights.py        # /summary, /brief, /insights/monthly, /timeline
api/v4/system.py          # /health, /metrics/trust, /agent-activity
```

Mechanical refactor, zero behavior change, locked by the existing ~505
backend tests passing unchanged. This is Phase 0 — every later phase touches
this file otherwise.

### 8.2 New endpoints

| Endpoint | Purpose |
|---|---|
| `GET /reports?status=pending` | Review queue of reports |
| `GET /reports/<id>` | Full report with sections + receipts |
| `POST /reports/<id>/resolve` | Batch resolution (§6) |
| `GET /workboard?group=space\|person&state=…` | Portfolio roll-up with derived states (§10.1) |
| `POST/PATCH/DELETE /markers…` | Follow-up markers |
| `POST /entities/<id>/pin` / `/unpin` | Explicit pin management |
| `POST /entities/<id>/promote` | theme→project only |
| `POST /entities/<id>/redact` | notes only |
| `POST /commitments/<id>/nudge-draft` | LLM-drafted nudge from receipts |
| `GET /insights/monthly` | Portfolio health briefing (computed on demand, cached in `AppSetting`) |

Retired: `POST /entities/<id>/convert` (replaced by `/promote`), auto-create
config surface.

## 9. UI architecture

- New shell in `ui/src/next/`, mounted at `/next` during build-out. React +
  Vite as today; CSS modules; no new framework.
- Surfaces per the vision IA: **Today, Workboard, Stream, Review, Spaces
  (Dossier), People**, omni-bar chrome (capture field, search/ask, review
  pulse count — *not* agent-run cards).
- One vocabulary module (`vocab.js`) translates v4 DTO terms → vision terms.
- Reuses the existing API client layer (`ui/src/api/`).
- **Cutover (Phase 6):** `/next` becomes `/`; then `ui/src/views/V5*`,
  `ui/src/lab/*`, and the legacy App views are **deleted** in the same
  phase — not kept as fallback. Three UI strata was the failure mode.
- No CRUD screens: every mutation in the new shell is a typed inline
  affordance writing a Ledger event (UX_VISION §5 invariants).

## 10. Derived signals

### 10.1 Workboard states

Computed per open task at query time (indexes on `due_at`, `updated_at`
suffice at single-operator scale; no materialization until proven needed):

- `mine` / `waiting_on`: owner vs. `operator_person_id`.
- `overdue`: `due_at < now()`.
- `stale`: no activity event in > staleness threshold (per-Space setting,
  default 10 days).
- `blocked`: open `blocks` link from an unresolved task.
- `at_risk` (v1 heuristics, tuned via TEST_PLAN metrics):
  - task: `stale` AND (due within 7d OR its Space has a finish line within 21d).
  - Space: finish line within 21d AND (≥50% of open tasks stale OR no Space
    activity in 14d).
  - Every flag carries a `reason` string and receipt refs. Flags use
    hysteresis (clears at threshold−2d) to avoid flapping.

Per-Space thresholds live in the project entity's `properties.thresholds`
(this is the "standing orders as settings" reduction).

### 10.2 Insight horizons

Same signals, three packagings (UX_VISION §4):

- **Daily** — `/today` extended: fired markers, ripened follow-ups, *newly*
  at-risk since yesterday (diff computed against a daily snapshot job).
- **Weekly** — existing `/summary` + brief machinery packaged as the Review
  digest: moved/decided/stalled/next, cited, exportable.
- **Monthly** — `/insights/monthly`: people quiet ≥21d, at-risk Spaces,
  themes idle past horizon, unowned open tasks. A briefing with citations;
  empty sections are omitted, and an empty briefing says nothing.

## 11. MCP alignment

New tools: `list_reports`, `get_report`, `resolve_report`, `get_workboard`,
`add_marker`, `draft_nudge`. Changed semantics: `capture` returns a
`report_id` to poll; `create_entity` from agents is always propose-tier
(server-enforced, not tool-arg-enforced). `append_activity_update` and
`submit_candidates` unchanged. MCP writes on behalf of the operator pin
fields only when `on_behalf=user` is explicit.

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Distillation quality can't cash the "one minute review" check | Phase 1 gate is *measured*: replay eval + review-time metric before any further surface work (TEST_PLAN §5) |
| Review volume rises when auto-create dies | Ships only with batch-accept; monitored via `metrics/trust` acceptance rate |
| Pinning logic sprawls | Single enforcement helper (`v4_trust.check_pin`); property-based tests over (field × actor × pin-state) |
| At-risk flags become wallpaper | Hysteresis + per-Space thresholds + monthly tuning pass against real portfolio (open question UX_VISION §9.7) |
| A fourth UI stratum lingers | Phase 6 deletes legacy UI in the same commit series that promotes `/next`; tracker carries it as an explicit exit criterion |
| Monolith regrows | Package split lands first (Phase 0); AGENTS.md rule: new routes go in the owning module |
