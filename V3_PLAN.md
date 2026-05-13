# Engram V3 — Build Plan

> Get the basics right. Fix what's broken, make what exists work, apply the design.
> No new features until all phases here are done.
>
> Track items with `[ ]` / `[~]` / `[x]`. Do not skip phases.

---

## Design System Reference

### Fonts
```css
--font-sans: 'IBM Plex Sans', sans-serif;
--font-mono: 'IBM Plex Mono', monospace;
/* Base: 13px, line-height 1.5 */
```

### Color tokens
```css
/* Light mode (default) */
--bg:           oklch(97.5% 0.014 88);
--surface:      oklch(100%  0.006 88);
--surface2:     oklch(95%   0.016 88);
--surface3:     oklch(91%   0.018 88);
--border:       oklch(87%   0.018 88);
--border-faint: oklch(92%   0.012 88);
--text:           oklch(18% 0.015 75);
--text-secondary: oklch(38% 0.012 75);
--text-muted:     oklch(58% 0.010 75);
--accent:     oklch(50% 0.14 278);
--accent-dim: oklch(93% 0.04 278);
--green:  oklch(40% 0.14 155);
--yellow: oklch(48% 0.14  82);
--red:    oklch(46% 0.18  22);
--pink:   oklch(46% 0.14 340);
--sidebar-w: 216px;
--topbar-h:  44px;

/* Dark mode — applied via [data-theme="dark"] on <html> */
--bg:          oklch(11%   0.016 272);
--surface:     oklch(14.5% 0.016 272);
--surface2:    oklch(18%   0.016 272);
--surface3:    oklch(22%   0.016 272);
--border:      oklch(26%   0.018 272);
--border-faint:oklch(20%   0.012 272);
--text:          oklch(93% 0.008 272);
--text-secondary:oklch(70% 0.010 272);
--text-muted:    oklch(48% 0.012 272);
--green:  oklch(68% 0.14 155);
--yellow: oklch(78% 0.14  82);
--red:    oklch(62% 0.18  22);
--pink:   oklch(68% 0.14 340);
```

### Entity type icons and colors
```
◈  project  → var(--accent)
◻  note     → var(--text-muted)
◆  task     → var(--yellow)
▲  area     → var(--pink)
◉  person   → var(--green)
⬡  resource → var(--text-muted)
```

### Typography scale
| Element | Size | Weight | Notes |
|---------|------|--------|-------|
| H1 (note) | 26px | 700 | letter-spacing -0.02em |
| H2 (note) | 15px | 600 | letter-spacing -0.01em |
| Body | 13.5px | 400 | line-height 1.7, --text-secondary |
| Card title | 12.5px | 500 | |
| Meta / label | 11–12px | 500–600 | IBM Plex Mono |
| Badges | 10–11px | — | IBM Plex Mono |

### Scrollbar
```css
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
```

---

## Status key
- `[ ]` Not started  |  `[~]` In progress  |  `[x]` Done

---

## Phase 0 — Fix Broken Flows

Silent failures in features the UI shows as complete. Nothing else starts until these pass.

### 0.1 Fix TipTap: save HTML, enable live markdown conversion
**Files:** `ui/src/components/Editor/TipTapEditor.tsx`, `ui/src/views/NoteDetailView.jsx`

The editor saves plain text. Every save destroys formatting. The vision requires live conversion as you type (type `# ` → H1 instantly, `**text**` → bold instantly).

- [ ] Install `@tiptap/extension-markdown` — handles live shortcut conversion and markdown load/save
- [ ] Configure with `transformPastedText: true` so pasted markdown renders immediately
- [ ] On save: use `editor.storage.markdown.getMarkdown()` to persist back to markdown, OR switch fully to HTML — pick one and be consistent
- [ ] `NoteDetailView.jsx:415` — change `onSave={async ({ text }) =>` to use the chosen format
- [ ] Remove the preview toggle button — WYSIWYG means no mode switch
- [ ] Verify slash commands still function after adding the extension (StarterKit + Markdown can conflict on `/`)

### 0.2 Fix AiSelectionPopover: wrong URL and field name
**File:** `ui/src/components/AiSelectionPopover/AiSelectionPopover.tsx:17`

- [ ] `/api/v1/ai/propose-from-selection` → `/api/v2/ai/propose-from-selection`
- [ ] Request body: `text: selectedText` → `selected_text: selectedText`

### 0.3 Replace fake AI panel with real call
**File:** `ui/src/components/Editor/TipTapEditor.tsx:63–86`

The AI panel generates `[AI: ${prompt}]` as a literal string.

- [ ] Replace with `fetch('/api/v2/ai/propose-from-selection', { action: 'improve_writing', selected_text: ... })`
- [ ] On success: replace selected text or append result to editor

### 0.4 Close AI tagging loop
**File:** `services/ai_pipeline.py:258`

`run_classify()` stores tags in `ai_meta` JSON but never writes `EntityTag` records. Tags are invisible everywhere.

- [ ] After `entity.ai_meta = ai_meta` (line 260): iterate `extraction.tags`, upsert `EntityTag` records using existing `Tag` model
- [ ] Add `tag_names` to `entity.to_dict()` response
- [ ] Confirm `NoteDetailView.jsx:455` (`note.tag_names`) now populates

### 0.5 Fix link resolution across all entity types
**Files:** `ui/src/views/NoteDetailView.jsx` (~line 556), `ui/src/components/ConnectionsPanel/ConnectionsPanel.jsx`

Both look up linked entities only in the `notes` array. Links to tasks, projects, or people show as `Note undefined`.

- [ ] Write `resolveEntity(id, store)` helper — searches `notes`, `tasks`, `projects`, `areas`, `people`, `resources`
- [ ] Replace all `resolveNote(id)` calls with the new helper
- [ ] Route each resolved link to the correct detail URL
- [ ] Show entity type icon (◈◻◆▲◉⬡) next to each link label

---

## Phase 1 — Cleanup & Field Name Migration

### 1.1 Remove unused views and routes
**Files:** `App.jsx`, `AppShell.jsx`, `ui/src/views/`, `ui/src/components/Kanban/`

Views that are cut from V3 should be deleted, not left in the nav as broken dead ends.

- [ ] Delete `ui/src/views/Graph.jsx`, `Graph.module.css`, `Graph.test.jsx`
- [ ] Delete `ui/src/views/Review.jsx`, `Review.module.css`, `Review.test.jsx`
- [ ] Delete `ui/src/views/MOCView.jsx`, `MOCView.module.css`, `MOCView.test.jsx`
- [ ] Delete `ui/src/components/Kanban/KanbanBoard.jsx`, `KanbanBoard.module.css`, `KanbanBoard.test.jsx`
- [ ] Remove `/graph`, `/review`, `/moc`, `/kanban` routes from `App.jsx`
- [ ] Remove Graph, Review, Maps nav items from `AppShell.jsx` `NAV_ITEMS`
- [ ] Remove all now-dead import statements

### 1.2 Migrate store and frontend from v1 to v2 field names
**Files:** `ui/src/stores/useStore.js`, `ui/src/api/engram.js`, all remaining view files

`name` → `title`, `raw_text` → `content`, `is_archived` → `lifecycle`

- [ ] Audit every field reference across all view and component files
- [ ] Update `ui/src/api/engram.js` request/response field names
- [ ] Update `useStore.js` action handlers
- [ ] Update all views: `Notes.jsx`, `NoteDetailView.jsx`, `Projects.jsx`, `ProjectFocus.jsx`, `Areas.jsx`, `AreaFocus.jsx`, `People.jsx`, `Tasks.jsx`, `Resources.jsx`, `ResourceDetail.jsx`, `Dashboard.jsx`, `Today.jsx`, `AppShell.jsx`, `CommandPalette.jsx`
- [ ] Remove v1 alias fields from `to_dict()` in `models.py` once frontend is clean
- [ ] Run test suite — this is a broad change, regressions are likely

---

## Phase 2 — Make Existing Views Work

These views exist but are broken or navigable to nothing. No new features — just make what was promised functional.

### 2.1 Tasks: real drag-and-drop kanban
**File:** `ui/src/views/Tasks.jsx`

The Tasks page has a kanban layout but uses ← → arrow buttons for status changes. `KanbanBoard.jsx` (dnd-kit) is at `/kanban`, unused.

Use native HTML5 drag (as in the design handoff — simpler, no extra dependency):
- [ ] Replace arrow buttons with `draggable` + `onDragStart` / `onDragOver` / `onDrop` column handlers
- [ ] Drop column highlight: `background: var(--surface2)` while dragging over
- [ ] Dragging card: `opacity: 0.35`
- [ ] On drop: `updateTask(id, { status: newStatus })`
- [ ] Quick-add input at bottom of each column (Enter to create, Escape to cancel)
- [ ] Remove `/kanban` route from `App.jsx`; delete or archive `KanbanBoard.jsx`

### 2.2 PersonFocus: make people navigable
**Files:** `ui/src/views/People.jsx`, new `ui/src/views/PersonFocus.jsx`, `App.jsx`

No `/people/:id` route. Clicking a person card does nothing.

- [ ] Create `PersonFocus.jsx`: name + role header, tabs for Notes / Tasks / Connections linked to this person
- [ ] Register `/people/:id` in `App.jsx`
- [ ] Make person cards in `People.jsx` navigate to `/people/:id`

### 2.3 ProjectFocus: show progress
**File:** `ui/src/views/ProjectFocus.jsx`

Current view is a document with a connections sidebar. No progress visibility.

- [ ] Add task status summary row at top: Done / In Progress / Pending as large mono numbers + 3px progress bar
- [ ] Restructure as: header (name, area, description, status, due date) → progress → tabs (Notes · Tasks · People · Connections)
- [ ] Tasks tab: mini 3-column grid (not full kanban), compact cards
- [ ] "Complete Project" button: `updateProject(id, { status: 'DONE' })`, shows "Rolling up…" → "✓ Completed"

### 2.4 ResourceDetail: works end-to-end
**Files:** `ui/src/views/ResourceDetail.jsx`, `ui/src/views/Resources.jsx`

Route exists in `App.jsx` but verify it actually fetches and renders.

- [ ] Load resource by `params.id` from API if not in store
- [ ] Make resource cards in `Resources.jsx` navigate to `/resources/:id`
- [ ] Show `reference_url` as a clickable link if set
- [ ] Show linked notes and tasks (simple lists, same pattern as ProjectFocus)

### 2.5 AreaFocus: show linked content
**File:** `ui/src/views/AreaFocus.jsx`

`AreaFocus.jsx` exists but likely shows nothing useful after v2 migration.

- [ ] After Phase 1 field name fix, verify `AreaFocus.jsx` loads and displays
- [ ] Show all projects in the area as a list with task count
- [ ] Show linked notes
- [ ] That's it — no full redesign needed here

---

## Phase 3 — AI: Close the Open Loops

These AI features were always supposed to work. Fixing broken wiring, not adding new features.

### 3.1 AI selection toolbar: visual fix + real wiring
**File:** `ui/src/components/AiSelectionPopover/AiSelectionPopover.tsx`

Phase 0.2 fixed the broken URL. This phase makes the UI match the design and the responses actually usable.

- [ ] Toolbar style (per handoff): `var(--surface3)` bg, border, 7px radius, `0 8px 24px rgba(0,0,0,0.55)` shadow, 3px padding
- [ ] Buttons: 11.5px, --text-secondary, no border, 5px radius, 4px 9px padding
- [ ] Actions: **Classify · Extract Task · Find Links · Improve** (4 buttons + ✕ close)
- [ ] Result panel: appears above toolbar, --surface bg, 1px accent-dim border, 11.5px accent mono text
- [ ] Position centered above selection rect
- [ ] "Extract Task" action: creates a task via `createTask({ title: selectedText })` in the store, shows confirmation in result panel
- [ ] "Classify" action: shows the returned classification result in the result panel
- [ ] "Improve" action: replaces selected text with the AI result in the editor

### 3.2 Quick Capture: entity type picker
**File:** `ui/src/components/capture/QuickCapture.jsx`

The design shows a type picker (note · task · resource · person). Currently only captures notes through the full ingestion pipeline regardless of type.

- [ ] Add type picker chips to the capture header: note / task / resource / person
- [ ] **note** (default): existing ingestion pipeline, unchanged
- [ ] **task**: `createTask({ title: text })` directly — skip ingestion pipeline
- [ ] **resource**: create entity with `entity_type=resource`, run background AI; toast "Saved as reference · AI classifying…"
- [ ] **person**: `createPerson({ title: text })` directly

---

## Phase 4 — Design: Apply the Handoff

Apply the design system from the handoff file. Match it precisely for the views that matter daily. Everything else (Graph, Review, MOC) just gets the CSS tokens applied — no separate redesign.

### 4.1 Global design system
**Files:** `ui/index.html`, `ui/src/index.css`

- [ ] Add Google Fonts: IBM Plex Sans (400/500/600/700) + IBM Plex Mono (400/500/600)
- [ ] Replace all CSS custom properties with the oklch values from the Design System Reference above
- [ ] `:root` = light mode; `[data-theme="dark"]` = dark mode overrides
- [ ] Base: `font-size: 13px; line-height: 1.5; font-family: var(--font-sans); -webkit-font-smoothing: antialiased`
- [ ] Global scrollbar (5px, transparent track, --border thumb, 3px radius)
- [ ] `button { font-family: inherit; }`
- [ ] Dark mode toggle: settings icon in topbar sets `document.documentElement.dataset.theme = 'dark'`, persists to `localStorage`
- [ ] Apply new tokens to all views that don't get a full redesign (Graph, Review, MOC, Areas, Inbox) — they inherit from global CSS, no extra work needed

### 4.2 AppShell
**Files:** `ui/src/components/layout/AppShell.jsx`, `AppShell.module.css`

- [ ] Sidebar: 216px expanded, 48px collapsed (icon-only rail), `transition: width 0.2s ease`
- [ ] Logo row (44px height): "engram" IBM Plex Mono 14px 700 letterSpacing -0.04em + collapse toggle
- [ ] Capture button: full width, --accent bg, 12px 600, "+" icon + "Capture" label (icon only when collapsed)
- [ ] Nav items: 12px icon + 12.5px label, 5px 8px padding, 5px radius; active: --accent-dim bg + --accent icon
- [ ] Pinned projects section (when expanded): "PINNED" 9.5px mono uppercase + project list (7px dot + truncated label)
- [ ] User avatar at bottom: 26px circle, --accent-dim bg, --accent text, 9px mono bold
- [ ] Topbar (44px, borderBottom): left view label (12px mono 600 --text-muted) + centered search trigger (--surface2, max 400px, ⌕ + ⌘K badge) + right icons
- [ ] Keyboard: `C` = capture, `Cmd+K` = command palette, `[` = toggle sidebar
- [ ] Remove the mobile bottom nav

### 4.3 Note detail view
**Files:** `ui/src/views/NoteDetailView.jsx`, `NoteDetailView.module.css`

- [ ] Layout: flex row, editor column (flex 1, borderRight) + AI sidebar (224px fixed)
- [ ] Breadcrumb: 11px --text-muted, padding 10px 32px 0
- [ ] Meta row: type chip (entity icon + label, 11px, --surface2, border, 4px radius) · dot · "Modified Xh ago" (11px mono) · word count
- [ ] Editor: TipTap WYSIWYG (from Phase 0.1), padding 8px 32px 32px, always editable, auto-save on blur 500ms debounce
- [ ] Connections section at bottom of editor column: borderTop, 2-col grid (Outgoing pills / Backlink rows)
- [ ] AI sidebar (224px, padding 16px 0):
  - Classification header: "AI · CLASSIFICATION" mono 10px + confidence badge (--accent)
  - Suggested tags: chips, click to accept (border --accent + --accent-dim bg when accepted)
  - Entity links found: type icon + label + confidence %
  - Quick actions: 4 buttons (Summarize / Extract tasks / Find related / Improve writing) — styled only for now; wire Summarize and Find related in a later sprint once basics are solid

### 4.4 Tasks view
**File:** `ui/src/views/Tasks.jsx` (functionality done in Phase 2.1, this is visual)

- [ ] Header: "Tasks" 17px 700 letterSpacing -0.02em + count badge (10px mono) + filter chips
- [ ] Board: flex row, no gap, columns `flex: 1`, `borderRight` between columns
- [ ] Column header: 7px colored dot + 12px 600 label + count + `+` button
- [ ] Cards: --surface bg, 1px --border, 6px radius, 10px 12px padding, cursor grab
  - Title: 12.5px 500
  - Bottom: project badge (10px mono, colored text + border) · due date (10px mono) · priority dot (6×6px)
- [ ] Quick-add: --surface2 bg, 1px --accent border, 6px radius; confirm: --accent bg

### 4.5 Project focus view
**File:** `ui/src/views/ProjectFocus.jsx` (structure done in Phase 2.3, this is visual)

- [ ] Header (padding 18px 28px 0): area badge (pink ▲, mono) · project name (22px 700 -0.025em) · description (12.5px --text-muted, max-width 520px) | status badge · due date · Complete button
- [ ] Progress: stat numbers (20px 700 mono -0.03em) + labels; progress track (3px, --surface2, --accent fill, 0.6s transition)
- [ ] Tabs: 12px 500, active = --text + 2px --accent bottom border
- [ ] Mini kanban in tasks tab: 3-col grid, compact cards (11.5px --text-secondary + 5×5px priority dot)

### 4.6 Today / Dashboard view
**File:** `ui/src/views/Today.jsx`

- [ ] Date heading: 22px 700 -0.025em letterSpacing
- [ ] Summary line: 12px mono --text-muted ("X tasks due today · Y in progress")
- [ ] Due Today: task rows with 14px checkbox + title + project badge + priority dot
- [ ] Recently Modified: type icon (entity color) + label + relative time

### 4.7 Command Palette
**File:** `ui/src/components/search/CommandPalette.jsx`

- [ ] Overlay: `rgba(0,0,0,0.55)`, `paddingTop: 120`, centered
- [ ] Panel: 520px, --surface, border, 10px radius, `0 24px 64px rgba(0,0,0,0.7)` shadow
- [ ] Input: ⌕ 18px + 15px input (transparent) + "ESC" badge (10px mono)
- [ ] Items: 13px --text-secondary + shortcut badge; borderBottom --border-faint

### 4.8 Capture modal
**File:** `ui/src/components/capture/QuickCapture.jsx` (functionality done in Phase 3.2, this is visual)

- [ ] Overlay: `rgba(0,0,0,0.55)`, centered
- [ ] Panel: 520px, --surface, border, 10px radius, `0 24px 64px rgba(0,0,0,0.7)` shadow
- [ ] Header: "QUICK CAPTURE" 12px mono uppercase --text-muted + type picker chips
- [ ] Type chips: 10.5px mono, border, 4px radius; active: --accent color + border + --accent-dim bg
- [ ] Textarea: transparent, no border, resize none, 14px sans, 1.65 line-height, min-height 120px
- [ ] Footer: "⌘↵ to save · ESC to cancel" (10px mono) + Save (12px 600, --accent bg, --bg text)

---

## Phase 5 — Minimum Viable Polish

Only items explicitly in the original vision. No extras.

### 5.1 Delete with cascade preview
**Vision:** "If you delete an object, you'd have the option to delete all linked objects with it, as long as they're not linked with anything else."
Backend `GET /api/v2/entities/:id/delete-preview` already exists.

- [ ] Before any entity deletion, call delete-preview
- [ ] If orphans exist: show modal listing them with "Delete linked" / "Keep linked" choice
- [ ] Pass `cascade=true/false` to the delete call

### 5.2 Follow-up date in Today view
**Vision:** base object has follow-up date as a core field.

- [ ] Today view: include entities with `follow_up_at = today`, not just tasks with `due_date`
- [ ] Entity cards: show follow-up date in mono when set (--yellow if overdue)
- [ ] Detail sidebar: allow setting/editing follow-up date inline

### 5.3 Test the closed loops
- [ ] Unit: `run_classify` creates `EntityTag` records (0.4)
- [ ] Unit: `callAiAction` sends to `/api/v2/` with `selected_text` (0.2)
- [ ] Unit: `TipTapEditor.onSave` emits correct format — not plain text (0.1)
- [ ] Integration: capture → classify → tag visible in AI sidebar
- [ ] Integration: task drag-and-drop updates status
- [ ] Integration: delete preview → cascade delete

---

## Execution Order

| Week | Phase | Goal |
|------|-------|------|
| 1 | 0 | All broken flows fixed and end-to-end tested |
| 2 | 1 | v1→v2 migration complete; v1 aliases removed |
| 3 | 2 | Kanban, PersonFocus, ProjectFocus, ResourceDetail, AreaFocus working |
| 4 | 3 | AI selection toolbar real, capture type picker wired |
| 5–6 | 4 | Design system applied across all views |
| 7 | 5 | Delete cascade, follow-up dates, test coverage |

---

## Explicitly out of scope for V3

These are features, not basics. Add to a backlog for after V3 ships.

- Inbox triage workflow
- "Find & Update existing entity" AI action
- Link proposal review UI
- Summarize / Find Related quick action wiring
- Graph / Review / MOC view redesigns (they get design tokens from 4.1, nothing more)
- MCP server changes
- Area full redesign (2.5 covers the minimum)
- Multi-user, offline sync, file attachments
