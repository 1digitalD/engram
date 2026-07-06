# Iteration 21 — Lab Surface (parallel UI, zero risk to current app)

Date: 2026-07-06
Status: **planned** (not started)
Owner: Engram
Predecessor: Iteration 20 (UI Context, Density & Color); design exploration in `docs/superpowers/` chat history (Engram Lab clickable prototype, disposable, not committed to repo).

## Why this iteration exists

A UX review (interview-driven, not a code audit) surfaced that Engram's core primitives are
mostly right — capture, reconciliation, entity linking, per-person meeting prep, per-person
load all exist and work. What's missing is **visibility and trust framing**, plus two small
aggregate gaps:

1. Capture applies changes silently; the reasoning behind a match/creation decision isn't
   visible at the moment of capture, so messy input isn't trusted enough to be captured
   regularly.
2. Entities don't expose a way to **manually add** a relationship (only remove exists,
   shipped in the prior UI-CTX work); the only way to link two entities today is via a new
   capture that happens to get auto-matched.
3. "Who's carrying what" requires opening each person's page one at a time — no rollup.

A disposable clickable prototype (Artifact, fake data) explored a redesigned shell covering
capture review, a post-commit receipt, standalone entity context, and a people/load rollup.
This iteration turns the validated parts of that prototype into a real, additive surface.

## Product decision (locked 2026-07-06)

- **New surface lives at `/lab/*`** inside the existing `ui/` React app — new files only,
  mounted via one additive `<Route path="/lab/*">` in `App.jsx`. No existing route,
  component, or behavior is modified. The current app remains the default landing
  experience (`/` → `/now`) and the permanent fallback — this iteration does not deprecate
  or replace anything.
- One additive touch to existing UI: a single "Try the redesign (beta)" link in the current
  `TopBar`, pointing at `/lab`. That is the only edit to a currently-shipped file in this
  entire iteration.
- **Lab writes to the same live data** the current app uses (not a sandbox/staging copy).
  A task created via Lab capture shows up in the current app and vice versa — one workspace,
  proven under real stakes, no dataset to reconcile later.
- **Explicitly cut from scope:** multi-person/group meeting prep. The prototype explored a
  "select N people → merged agenda" view; this is **not** being built. Lab ships the
  single-person meeting-prep + current-load pattern only (same as today), plus a people-list
  rollup for scanning load across people — no merge/aggregation across attendees.
- Backend changes are additive-only, per `docs/V4_PRINCIPLES.md`: new functions, new routes,
  TDD, no modification of existing handlers' required behavior. Two new endpoints are needed
  (see LAB-02); everything else reuses existing `/api/v4` routes already consumed by the
  current UI.

## Non-goals

- No group/multi-person meeting prep (cut, see above).
- No schema migrations. `EntityLink` already supports what's needed.
- No deprecation, redirect, or behavior change to any existing `/now`, `/threads`, `/notes`,
  `/projects`, `/tasks`, `/areas`, `/people`, `/resources` route.
- No change to required fields in existing API response shapes — only additive fields where
  needed (LAB-01).
- No decision yet on whether Lab ever becomes the default UI — out of scope for this
  iteration; revisit after LAB-03 ships and gets real usage.

## Milestones

| Milestone | Slices | Ship criteria |
|-----------|--------|----------------|
| **M1 — Shell scaffold** | LAB-00 | `/lab` renders real Today/entity-list/search data; reachable only via TopBar link; existing routes byte-for-byte unchanged |
| **M2 — Capture trust loop** | LAB-01 | Real capture, real reconciliation reasoning visible pre- and post-commit, real undo |
| **M3 — Entity authoring** | LAB-02 | Inline attribute edit + manual relationship add against real data |
| **M4 — People rollup** | LAB-03 | Load/last-heard/quiet-flag visible across all people without opening each page |

Recommended order: M1 → M2 → M3 → M4, strictly sequential — each milestone's acceptance
criteria must pass before the next starts, matching existing slice discipline.

---

## Slice specifications

### LAB-00 — Shell scaffold + real read data (M1)

**Scope:**
- New files under `ui/src/lab/` only: `LabShell.jsx` (sidebar + topbar + `/lab/*` sub-routes),
  `LabToday.jsx`, `LabEntityList.jsx`, `LabSearch.jsx` (search overlay).
- Mount `<Route path="/lab/*" element={<LabShell />} />` in `App.jsx` — additive line, no
  existing `<Route>` touched.
- All screens read through the existing `v4API` client (`ui/src/api/v4Client.js`) against
  real `/api/v4/today`, `/api/v4/entities`, `/api/v4/search` — no new backend code in this
  slice.
- One-line addition to current `TopBar.jsx`: a "Try the redesign (beta)" link to `/lab`.
- No writes in this slice — Capture button in Lab shell is present but disabled/"coming in
  LAB-01" to keep the slice read-only and low-risk.

**Acceptance criteria:**
- Visiting `/now`, `/tasks`, `/people`, etc. (existing routes) renders identically to before
  this slice — no diff in existing component files.
- `/lab` renders the shell with real Today data, real entity lists, and a working `Cmd+K`
  search overlay backed by real hybrid search results.
- TopBar link is the only diff in a previously-shipped file; covered by an existing
  `TopBar.test.jsx` snapshot/assertion update.
- `cd ui && npm test && npm run build` green.

**Risk:** low (additive routes/files; one one-line edit to a shared, well-tested component).

---

### LAB-01 — Capture trust loop, real data (M2)

**Scope:**
- `LabCapture.jsx` sheet, wired to real `POST /api/v4/capture` (`mode: "auto"`), rendering
  the real `applied_changes` / `suggestions` response as the review → receipt flow from the
  prototype.
- Backend: additive-only enrichment of the existing capture response — add a `reason` /
  `match_confidence` / `matched_entity` field to each item in `applied_changes` and
  `suggestions` where not already present (check `_capture_result_payload` first; some of
  this may already be there from Iteration 19's signal-quality work — confirm before adding
  anything new). **No existing field is renamed or removed.**
- Per-item Undo reuses the existing `GET /api/v4/entities/:id/capture-changes` +
  `POST /api/v4/events/:id/revert` pair (Slice B3, already shipped) — no new revert logic.

**Acceptance criteria:**
- A contract test asserts every field present in the capture response *before* this slice
  is still present and unchanged in shape/type after — protects the current UI's
  `V5CaptureSheet`/`V5ReviewSheet`, which also consume this endpoint.
- Real capture of a fixture note in Lab shows auto-applied items with visible match
  reasoning, and ambiguous items as resolvable inline (matches the prototype's expand/fix
  pattern), then a receipt with working Undo.
- `pytest` (capture + suggestions integration suites) and `npm test -- LabCapture` green.

**Risk:** medium — the only slice touching a response shape shared with existing UI. Mitigate
with the contract test above before writing any new field.

---

### LAB-02 — Entity authoring: inline edit + manual relationship add (M3)

**Scope:**
- `LabEntityDetail.jsx`, wired to the existing entity-detail GET and the existing
  update-entity PATCH (already used by current UI's edit mode) for status/priority/date.
- **New additive endpoint:** `POST /api/v4/entities/:id/links` — body
  `{ target_id, relationship_type }`. Reuses the existing `_create_entity_link` helper
  (`api/v4_entities.py`); adds request validation (valid `relationship_type` per
  `V4_PRINCIPLES.md` allowed list, entity-type compatibility, `blocks`-cycle rejection reusing
  the existing cycle-detection logic from Phase C4 delegation work). Source is recorded as
  `manual`/user actor, not `agent:*`.
- "+ add" picker in the UI calls existing hybrid search for candidate lookup, then the new
  link endpoint on selection.

**Acceptance criteria:**
- New endpoint has unit + integration tests written first (red → green): valid link creates
  an `EntityLink` row; invalid `relationship_type` rejected with a clear error; cyclic
  `blocks` link rejected; existing link-creation code paths (`_create_entity_link` callers)
  unaffected.
- In Lab, editing status/priority/date on a real task persists and is reflected on that same
  entity's page in the *current* app (proves shared data, no divergence).
- Adding a relationship via the "+ add" picker creates a real `EntityLink`, visible as a chip
  in both Lab and (once that entity type's detail page is next opened) the current app.
- `pytest tests/integration/test_v4_entity_links.py` (new) and `npm test -- LabEntityDetail`
  green.

**Risk:** low — new route, new file, reuses existing validated helper; no existing endpoint
modified.

---

### LAB-03 — People rollup (M4)

**Scope:**
- `LabPeople.jsx`: list of people showing open-task count, last-heard timestamp, and a
  "gone quiet" flag (reusing the existing delegation-cadence logic from `_person_pulse` /
  `_delegation_cadence_days`, already computed for Today's "needs a nudge" section).
- No new aggregation endpoint if per-person data can be assembled from the existing
  `/api/v4/entities?type=person` list plus each person's existing detail payload; add a
  small additive batch endpoint (`GET /api/v4/people/load-summary`) **only if** N+1 calls
  prove too slow in practice (measure first, don't pre-optimize).
- Clicking a person still opens their existing single-person detail (meeting prep +
  current load) — unchanged from what ships today, just reachable from Lab's shell too.
- **Explicitly not built:** multi-select, "prep meeting for selected", any merge/aggregation
  across more than one person's data. Cut per product decision above.

**Acceptance criteria:**
- People list in Lab shows real load/last-heard/quiet-flag for every real person, computed
  from real data.
- No multi-select UI exists on this screen.
- If a batch endpoint was added: it's additive-only, and a perf test shows meaningful
  improvement over N+1 before it's kept.
- `npm test -- LabPeople` green; relevant backend suite green if a new endpoint was added.

**Risk:** low.

---

## Rollout / deploy notes

- Each slice: worktree per slice, TDD, full backend + frontend suite green, merged to `main`
  fast-forward — same discipline as `docs/V4_WORLD_MODEL_PLAN.md` and Iteration 19/20.
- Because LAB-01 onward writes real data, snapshot before merging that slice's deploy:
  `bash scripts/backup_prod.sh`, per `V4_PRINCIPLES.md` production data safety rules — same
  as any other change touching live data, Lab or not.
- Deploy cadence: end of each milestone (not per-slice), smoke-test `GET /api/v4/health`,
  `GET /api/v4/today`, one capture round-trip, **plus** one `/lab` smoke pass per milestone.
- Since `/lab` is reachable only via an explicit TopBar link, it can ship to production
  after each milestone without being "launched" — it's opt-in by construction until a
  separate decision is made to promote it.

## Session handoff checklist

When resuming:
1. Read this file + `EXECUTION-TRACKER.md` for current slice status.
2. Pick the earliest unchecked slice in milestone order (LAB-00 → LAB-01 → LAB-02 → LAB-03).
3. Run that slice's validation commands before marking acceptance.
4. Update acceptance checkboxes and the tracker.
