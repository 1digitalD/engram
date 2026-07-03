# Iteration 20 — UI Context, Density & Color

Date: 2026-07-03  
Status: **in progress** (UI-CTX-01–03 deployed; next: UI-CTX-05)  
Owner: Engram  
Predecessor: Post-iteration UI density pass (task list context chips, compact layouts)

## UX assessment (information density + usability)

### What works today
- **Compact list rows** on Tasks/Now/Threads — good vertical density without losing scanability.
- **EntityContextChips** — project/area context is the highest-signal metadata for tasks; chips beat inline prose.
- **Design tokens** (`--entity-*`) — color system exists; underused on list surfaces.

### Density gaps (ranked by daily impact)
| Surface | Problem | UX impact |
|---------|---------|-----------|
| **Recall (⌘K)** | Was parsing wrong API shape → empty results | Primary nav broken; highest severity |
| **Thread detail actions** | Task title only, no parent context | User must open task to know where it lives |
| **Recall results** | Title + status only; no snippet | Wasted vertical space; low discrimination between similar titles |
| **Project/area lists** | `task_counts` / `linked_counts` ignored | Lists feel empty; user opens each row to learn load |
| **Task assignee** | API sends `people[]`; UI ignores | Hard to triage delegation from list views |
| **TopBar** | No link to `/tasks`, `/projects` | Entity lists are URL-only; Recall is only discovery path |

### Color treatment principles (this iteration)
Use color **semantically**, not decoratively:

1. **Entity-type accent** — 2px left border + group dot using `--entity-{type}` (Recall, future: all list rows).
2. **Context chips** — tinted border/text per type (project purple, area pink) — already on task cards.
3. **Status semantics** — blocked=red, waiting=yellow, done=muted (Recall first; extend to task list badges).
4. **Attention bands** — keep existing hot/warm left borders on Now/Threads; don't add competing color systems.

Avoid: full-row background fills, rainbow badges, or color without a semantic meaning.

### Usability guardrails
- Never nest `<a>` inside `<a>` — context chips live outside primary row links (already done on task list).
- Snippets truncate with ellipsis; full text on detail page.
- Touch targets stay ≥44px on action buttons; list rows can stay compact (entire row is clickable).
- Color never the only signal — always pair with text/icon (glyph + label).

## Non-goals
- No schema migrations.
- No new top-level lenses without product sign-off (see UI-CTX-09).
- No full design system rewrite.

## Milestones

| Milestone | Slices | Ship criteria |
|-----------|--------|---------------|
| **M1 — Broken surfaces** | UI-CTX-01 | Recall returns real results; snippets + type color visible |
| **M2 — Context propagation** | UI-CTX-02, UI-CTX-03 | Task parent context on detail + search surfaces |
| **M3 — List richness** | UI-CTX-04, UI-CTX-05 | Assignee + counts on list rows |
| **M4 — Color system rollout** | UI-CTX-06 | Shared row chrome across Now/Tasks/Recall |
| **M5 — Product decisions** | UI-CTX-07, UI-CTX-08 | Nav + project parent area (needs input) |

Recommended order: M1 → M2 → M3 → M4. M5 blocked on user decisions.

---

## Slice specifications

### UI-CTX-01 — Recall search fix + density/color (M1) — **done (2026-07-03)**

**Problem:** `V5Recall` read `response.data`; API returns `{ results: [{ entity, match }] }`. Tests mocked wrong shape.

**Changes:**
- `normalizeSearchResults()` utility + unit tests
- `v4API.search` adds normalized `data` field
- Recall shows match snippet, entity-type left border, semantic status pills, grouped headers with count

**Validation:**
```bash
cd ui && npm test -- searchResults V5Recall && npm run build
```
Manual: ⌘K → search known task → result appears with snippet.

**Acceptance:** [x] Recall shows results from real API shape [x] Snippet visible [x] Type color on rows

---

### UI-CTX-02 — Backend task context on detail + search (M2) — **done (2026-07-03)**

**Acceptance:** [x] Person detail `current_load[].task.projects` populated [x] Search task hit includes projects

---

### UI-CTX-03 — Thread detail + Recall context chips (M2) — **done (2026-07-03)**

**Acceptance:** [x] Action row shows project/area/people [x] Recall task shows chips outside result button

---

### UI-CTX-04 — Assignee chips on task surfaces (M3) — **done (merged into UI-CTX-03)**

**Acceptance:** [x] All assignees visible on task cards when `people[]` exists

---

### UI-CTX-05 — List row metadata richness (M3)

**Changes:**
- Project rows: show `task_counts.open` / `task_counts.total` badge
- Area/person rows: show `linked_counts` summary (e.g. "3 tasks · 2 projects")

**Acceptance:** [ ] Project list shows open task count [ ] Area list shows link counts

---

### UI-CTX-06 — Shared list row color chrome (M4)

**Changes:**
- Extract shared `EntityListRow` styles: type left-border, status semantic pills
- Apply to `V5EntityList`, `V5Now` rows, `V5Threads`/`V5EntityRow`

**Acceptance:** [ ] Task row in Now has same type accent as Tasks list

---

### UI-CTX-07 — Project parent area (M5) — **needs backend**

**Problem:** No `_attach_project_context`; projects don't expose parent area on list API.

**Blocked until:** New `_attach_project_context` helper (parent area link).

---

### UI-CTX-08 — TopBar entity list nav (M5) — **deferred (user: 2026-07-03)**

**Decision:** Leave TopBar as-is. Recall remains primary discovery for entity lists.

---

### UI-CTX-04 — Assignee chips on task surfaces (M3)

**Decision (user: 2026-07-03):** Show **all** assignees (`people[]`), not first-only.

---

### UI-CTX-09 — Polish deferrals (backlog)

- `--fab-clearance` CSS variable
- Desktop `inlineButton` sizing on thread detail
- Memory timeline → `XGlyph`
- Wire or remove unused `CardActions`

---

## Session handoff checklist

When resuming:
1. Read this file + `EXECUTION-TRACKER.md` for current slice status.
2. Pick earliest unchecked slice in milestone order.
3. Run slice validation commands before marking acceptance.
4. Update acceptance checkboxes and tracker date.

## Color recommendations (user asked 2026-07-03)

Apply in **UI-CTX-06** unless noted earlier:

| Treatment | Where | Implementation |
|-----------|-------|------------------|
| **Colored glyphs** | All list rows | Wrap `XGlyph` in a 20px circle with `color-mix(--entity-{type} 12%, transparent)` background; glyph uses `--entity-{type}` |
| **Status pills** | Tasks list, Now, Recall | Extend Recall pattern: `open`=neutral, `in_progress`=accent tint, `blocked`=red, `waiting`=yellow, `done`=muted |
| **Due-date urgency** | Task rows | Overdue left border or pill uses `--red`; due-today uses `--yellow`; else muted |
| **Attention bands** | Now hot/warm | Keep existing red/yellow left borders; add faint `background: color-mix(var(--red) 4%, var(--surface))` on hot rows only |
| **Context chips** | Tasks (done) | Project/area chips keep tinted border; **people chips** use `--entity-person` (UI-CTX-04) |
| **Group headers** | Recall, future grouped lists | Colored dot + count badge (Recall done) |
| **Project load badge** | Project list (UI-CTX-05) | `"3 open"` pill in `--entity-project` when `task_counts.open > 0` |

Avoid: rainbow rows, saturation on body text, color-only status without label.

## Resolved decisions (2026-07-03)

1. **TopBar nav:** Leave as-is (Recall-only discovery).
2. **Assignees:** Show all on task cards (UI-CTX-04).
3. **Color:** Use accents/glyphs/pills per table above in UI-CTX-06 rollout.
