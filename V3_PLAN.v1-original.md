# Engram V3 — Build Plan

> Source of truth for all V3 work. Updated from Claude Design handoff (engram-handoff.zip).
> Track items with `[ ]` / `[~]` / `[x]`. Do not skip phases — each builds on the previous.

---

## Design System Reference

Extracted directly from the handoff files:

### Fonts
```css
--font-sans: 'IBM Plex Sans', sans-serif;
--font-mono: 'IBM Plex Mono', monospace;
/* Base: 13px, line-height 1.5 */
```

### Color tokens (light mode default)
```css
--bg:           oklch(97.5% 0.014 88);
--surface:      oklch(100%  0.006 88);
--surface2:     oklch(95%   0.016 88);
--surface3:     oklch(91%   0.018 88);
--border:       oklch(87%   0.018 88);
--border-faint: oklch(92%   0.012 88);
--text:           oklch(18% 0.015 75);
--text-secondary: oklch(38% 0.012 75);
--text-muted:     oklch(58% 0.010 75);
--accent:     oklch(50% 0.14 278);   /* blue-purple */
--accent-dim: oklch(93% 0.04 278);
--green:  oklch(40% 0.14 155);
--yellow: oklch(48% 0.14  82);
--red:    oklch(46% 0.18  22);
--pink:   oklch(46% 0.14 340);
--sidebar-w: 216px;
--topbar-h:  44px;
```

### Dark mode overrides (via JS toggle, not default)
```css
--bg:          oklch(11%   0.016 272);
--surface:     oklch(14.5% 0.016 272);
--surface2:    oklch(18%   0.016 272);
--surface3:    oklch(22%   0.016 272);
--border:      oklch(26%   0.018 272);
--border-faint:oklch(20%   0.012 272);
--text:          oklch(93% 0.008 272);
--text-secondary:oklch(70% 0.010 272);
--text-muted:    oklch(48% 0.012 272);
/* green/yellow/red/pink get lighter in dark mode */
--green:  oklch(68% 0.14 155);
--yellow: oklch(78% 0.14  82);
--red:    oklch(62% 0.18  22);
--pink:   oklch(68% 0.14 340);
```

### Entity type system
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
| Body text | 13.5px | 400 | line-height 1.7, --text-secondary |
| Task text | 13px  | 400 | line-height 1.5 |
| Card title | 12.5px | 500 | |
| Meta / label | 11–12px | 500–600 | often IBM Plex Mono |
| Badges/chips | 10–11px | — | IBM Plex Mono |

### Global scrollbar
```css
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
```

---

## Status key
- `[ ]` Not started
- `[~]` In progress
- `[x]` Done

---

## Phase 0 — Fix Broken Flows

These are silent failures in features the UI already shows as complete. **Do not start Phase 1 until all of Phase 0 is done.**

### 0.1 Fix TipTap content format (core note save/load)
**Files:** `ui/src/components/Editor/TipTapEditor.tsx`, `ui/src/views/NoteDetailView.jsx`

The editor saves `text` (plain), the DB stores `raw_text` (markdown string), TipTap expects HTML/JSON. Every round-trip destroys formatting.

- [ ] Install `@tiptap/extension-markdown` (provides markdown→HTML on load and getMarkdown() on save, or use `marked` + `turndown`)
- [ ] On editor init: convert `initialContent` markdown string → HTML before passing to TipTap `content` prop
- [ ] On save: call `editor.getHTML()` — not `editor.getText()`
- [ ] Update `NoteDetailView.jsx:415`: change `onSave={async ({ text }) =>` to `onSave={async ({ html }) =>` and persist `{ content: html }`
- [ ] Render note body with `dangerouslySetInnerHTML` (+ DOMPurify sanitize) instead of `<ReactMarkdown>` for the read/display path
- [ ] Remove the edit/preview toggle button — WYSIWYG means no mode switch

### 0.2 Fix AiSelectionPopover API call
**File:** `ui/src/components/AiSelectionPopover/AiSelectionPopover.tsx:17`

Wrong URL (v1 not v2), wrong field name (`text` not `selected_text`).

- [ ] Change URL: `/api/v1/ai/propose-from-selection` → `/api/v2/ai/propose-from-selection`
- [ ] Change body field: `text: selectedText` → `selected_text: selectedText`
- [ ] Verify backend `api/ai_selection.py` returns `{ result, entity, action }` shape

### 0.3 Remove fake AI panel
**File:** `ui/src/components/Editor/TipTapEditor.tsx:63–86`

The `AIPanel` component generates `[AI: ${prompt}]` literally instead of calling the backend.

- [ ] Replace the simulated response with a real `fetch` to `/api/v2/ai/propose-from-selection`
- [ ] Action: `improve_writing`; body: `{ selected_text: selectedContent, action: 'improve_writing' }`
- [ ] On success: replace selection or append AI result to editor
- [ ] Show real response, not the echoed prompt string

### 0.4 Close the AI tagging loop
**File:** `services/ai_pipeline.py:258`

`run_classify()` stores `extraction.tags` in `ai_meta["extracted_tags"]` (JSON blob) but never writes `EntityTag` records. Tags are invisible everywhere.

- [ ] After line 260 (`entity.ai_meta = ai_meta`), iterate `extraction.tags` and upsert `EntityTag` records using the existing `Tag` model + deduplication from `api/tags.py`
- [ ] Add `tag_names` to the entity `to_dict()` response
- [ ] Confirm `NoteDetailView.jsx:455` (`note.tag_names`) now shows real data

### 0.5 Fix entity link resolution across all types
**Files:** `ui/src/views/NoteDetailView.jsx` (~line 556), `ui/src/components/ConnectionsPanel/ConnectionsPanel.jsx`

Both resolve entity links only by searching the `notes` array. Links to tasks/projects/people render as `Note undefined`.

- [ ] Write a `resolveEntity(id, store)` helper that searches `notes`, `tasks`, `projects`, `areas`, `people`, `resources`
- [ ] Use it everywhere link resolution currently uses `resolveNote(id)` alone
- [ ] Route each link to the correct detail URL based on resolved entity type
- [ ] Show the entity type icon (◈◻◆▲◉⬡) next to each link label

---

## Phase 1 — Core Feature Completion

### 1.1 Wire real drag-and-drop into Tasks page
**Files:** `ui/src/views/Tasks.jsx`

> **Design note:** The handoff prototype uses native HTML5 drag (`draggable`, `onDragStart`, `onDragOver`, `onDrop`) — not dnd-kit. Use the same approach; simpler, no extra dependency. `KanbanBoard.jsx` (dnd-kit) is unused at this point and should be removed or left archived.

- [ ] Replace arrow-button status change in `Tasks.jsx` with native HTML5 drag columns
- [ ] Three columns: Pending · In Progress · Done (dots colored --text-muted / --yellow / --green)
- [ ] Column header: colored dot + label + count + `+` add button
- [ ] Quick-add inline input below column header (Enter to create, Escape to cancel)
- [ ] Card design (per design spec):
  - Title: 12.5px, fontWeight 500
  - Bottom row: project badge (mono, colored border + text) · due date (mono, 10px) · priority dot (6×6px, --red / --yellow / --text-muted)
- [ ] Dragging card: opacity 0.35 on source; drop column gets `background: var(--surface2)` highlight
- [ ] Filter bar above board: All / By Project / Overdue chips
- [ ] On drop: call `updateTask(id, { status: newStatus })`
- [ ] Remove `/kanban` route from `App.jsx`; remove `KanbanBoard` import

### 1.2 Add PersonFocus detail view
**Files:** `ui/src/views/People.jsx`, new `ui/src/views/PersonFocus.jsx`, `App.jsx`

No `/people/:id` route exists. Clicking a person does nothing.

- [ ] Create `PersonFocus.jsx`:
  - Header: name, role, initials avatar (32px circle, accent-dim bg, accent text)
  - Tabs: Notes · Tasks · Projects · Connections (same tab style as ProjectFocus)
  - Notes tab: list of notes linked to this person
  - Tasks tab: list of tasks linked to this person
  - AI sidebar: 224px, same structure as note AI sidebar (tags, suggested links, quick actions)
- [ ] Register `/people/:id` route in `App.jsx`
- [ ] Make person cards in `People.jsx` navigable (click → `/people/:id`)
- [ ] `setActivePerson` in store when navigating to person focus

### 1.3 Redesign ProjectFocus to match design spec
**File:** `ui/src/views/ProjectFocus.jsx`

Current view is a document with a connections sidebar. Design shows a structured header with progress metrics.

- [ ] Header (padding 18px 28px 0, borderBottom):
  - Left column: area badge (pink ▲), project name (22px, letterSpacing -0.025em), description (12.5px, --text-muted, max-width 520px)
  - Right column: status badge (6px dot + text), due date (mono), "Complete Project" button
- [ ] Progress section (below header text, above tabs):
  - Stat numbers: Done / In Progress / Pending as 20px bold mono numbers with small labels
  - Percentage right-aligned (12px mono, --text-muted)
  - 3px progress track (--surface2 bg, --accent fill, transition 0.6s)
- [ ] Tabs: Notes · Tasks · People · Connections (12px, bottom border 2px --accent when active)
- [ ] **Notes tab:** list rows (◻ icon + title + modified time + tag chips + "New note" dashed button)
- [ ] **Tasks tab:** mini 3-column grid (not full kanban), compact cards per design spec
- [ ] **People tab:** person cards with initials avatar, name, role; "Add person" dashed button
- [ ] **Connections tab:** list of linked entities with type icon + label + type label
- [ ] "Complete Project" button: calls `updateProject(id, { status: 'DONE' })`, shows "Rolling up…" → "✓ Completed" state transition

### 1.4 Verify and fix ResourceDetail
**Files:** `ui/src/views/ResourceDetail.jsx`, `ui/src/views/Resources.jsx`

Route exists in `App.jsx` but verify the detail view actually fetches and renders data end-to-end.

- [ ] Confirm `ResourceDetail.jsx` loads entity by `params.id` (from API if not in store)
- [ ] Make resource cards in `Resources.jsx` navigate to `/resources/:id`
- [ ] Add linked notes, tasks, and people sections (same pattern as ProjectFocus tabs)
- [ ] Add the 224px AI sidebar (tags, suggested links, quick actions)

---

## Phase 2 — AI Feature Completion

### 2.1 AI text selection toolbar (match design exactly)
**Files:** `ui/src/components/AiSelectionPopover/AiSelectionPopover.tsx`

Design shows a compact floating toolbar above the selection, with 4 action buttons and a result box above the toolbar.

- [ ] Toolbar background: `var(--surface3)`, border, borderRadius 7px, boxShadow `0 8px 24px rgba(0,0,0,0.55)`, padding 3px, gap 2px
- [ ] Button style: 11.5px, fontWeight 500, --text-secondary, no background, borderRadius 5px, padding 4px 9px, hover gets slight bg
- [ ] Four actions: **Classify · Extract Task · Find Links · Improve** (matching design labels)
- [ ] Close button (✕) at right end
- [ ] Result panel: appears above toolbar, --surface bg, 1px accent-dim border, 5px radius, 6px 10px padding, 11.5px accent mono text, shadow
- [ ] Position: centered above selection rect, `top: rect.top - (result ? 80 : 44)`

### 2.2 AI selection: "update existing entity" path
**Files:** `ui/src/components/AiSelectionPopover/AiSelectionPopover.tsx`, `api/ai_selection.py`

Currently only creates new entities. Vision requires ability to update an existing one.

- [ ] Add `find_and_update` to AI_ACTIONS (label: "Find & Update")
- [ ] Backend handler in `api/ai_selection.py`: semantic search against existing entities with the selected text; return top 3 candidates
- [ ] Frontend: when action is `find_and_update`, show disambiguation panel listing candidate entities + proposed change; "Apply" / "Dismiss" per candidate
- [ ] "Apply": `PATCH /api/v2/entities/:id` with the proposed update

### 2.3 Wire link proposal review UI
**Files:** `ui/src/views/NoteDetailView.jsx`, `api/proposals.py`

`run_autolink` stores link candidates (confidence < 0.92) in `ai_meta["link_proposals"]`. The `/api/v2/proposals` endpoint exists. No UI surfaces them.

- [ ] Add "Suggested Links" section to the 224px AI sidebar (note, project, person focus views)
- [ ] Show each candidate: type icon + entity name + confidence %
- [ ] "Accept" button → `POST /api/v2/links` (creates the EntityLink)
- [ ] "Dismiss" button → removes from proposals list
- [ ] Lower auto-apply threshold in `services/link_proposer.py` from 0.92 → 0.80 (most content never reaches 0.92)

### 2.4 Quick Capture: entity type selector
**File:** `ui/src/components/capture/QuickCapture.jsx`

Design shows a type picker in the capture modal (note · task · resource · person). Currently only captures notes.

- [ ] Add type picker to `QuickCapture` header row (four chips: note / task / resource / person)
- [ ] Active chip: accent color + accent-dim background + accent border
- [ ] Inactive chip: mono font, --text-muted, --border border
- [ ] When type is `resource`: skip structured classification, create with `entity_type=resource`, let background AI pipeline handle tagging/linking; toast: "Saved as reference · AI classifying…"
- [ ] When type is `task`: quick-create task with title from textarea, skip ingestion pipeline
- [ ] When type is `person`: quick-create person entity

---

## Phase 3 — Design Overhaul

Implement the design system from the handoff exactly. This replaces all current CSS custom properties and font loading.

### 3.1 Global design system
**Files:** `ui/index.html`, `ui/src/index.css`

- [ ] Add Google Fonts link for IBM Plex Sans + IBM Plex Mono (weights 400, 500, 600, 700 for sans; 400, 500, 600 for mono)
- [ ] Replace all CSS custom properties in `index.css` with the exact oklch values from the design spec (light mode as `:root`, dark mode as `[data-theme="dark"]`)
- [ ] Set `font-size: 13px; line-height: 1.5; font-family: var(--font-sans); -webkit-font-smoothing: antialiased`
- [ ] Global scrollbar: 5px width, transparent track, `var(--border)` thumb, 3px radius
- [ ] `button { font-family: inherit; }` global reset
- [ ] Add `--sidebar-w: 216px` and `--topbar-h: 44px` to `:root`
- [ ] Implement dark mode toggle: a `<html data-theme="dark">` attribute controlled by a settings button; persist to `localStorage`

### 3.2 AppShell redesign
**Files:** `ui/src/components/layout/AppShell.jsx`, `AppShell.module.css`

- [ ] **Sidebar** (216px expanded, 48px collapsed, `transition: width 0.2s ease`):
  - Logo row (height: 44px = topbar-h): "engram" in IBM Plex Mono 14px, fontWeight 700, letterSpacing -0.04em + collapse toggle (← / →)
  - **Capture button**: full width, accent bg (`oklch(98% 0.005 272)` text in dark / white-ish), 6px radius, 7px 10px padding, 12px bold, gap 6px, "+" icon 16px + "Capture" label (hidden when collapsed)
  - **Nav items**: icon 12px centered (14px width), label 12.5px, padding 5px 8px, borderRadius 5px; active: accent-dim bg + accent icon color; collapsed: center-aligned, 7px all-around padding
  - Nav icons use the entity icon system: ◈ Today, ⬡ Inbox (with badge count), ◻ Notes, ◈ Projects, ▲ Areas, ◆ Tasks, ⬡ Resources, ◉ People, ⬡ Graph
  - **Inbox badge**: 10px mono, accent color, accent-dim bg, borderRadius 10px
  - **Pinned section** (visible when expanded): "PINNED" uppercase 9.5px mono label + list of project items (7px colored dot + 12px label, truncated)
  - **Bottom**: user avatar (26px circle, accent-dim bg, accent text, 9px mono bold) + user name
- [ ] **Topbar** (44px height, borderBottom --border, bg --bg):
  - Left (80px): view label (12px, fontWeight 600, --text-muted, IBM Plex Mono, letter-spacing 0.04em)
  - Center: search trigger button (max 400px, --surface2 bg, border, 6px radius, 5px 10px padding, ⌕ icon 14px + "Search or jump to…" 12px + ⌘K badge)
  - Right (80px): notification icon with 5px accent dot + settings icon
- [ ] **Keyboard shortcuts**: `C` → open capture; `Cmd+K` → command palette; `[` → toggle sidebar collapse
- [ ] Remove mobile bottom nav

### 3.3 Note detail view redesign
**Files:** `ui/src/views/NoteDetailView.jsx`, `NoteDetailView.module.css`

Match the handoff `views/note.jsx` exactly:

- [ ] **Layout**: `display: flex; height: 100%; overflow: hidden;` — editor column (flex 1, borderRight) + AI sidebar (224px, fixed width, overflowY auto)
- [ ] **Breadcrumb** (10px 32px 0): area/project context → "Notes" → note title, 11px --text-muted
- [ ] **Meta row** (8px 32px 12px): type chip (entity icon + type name, 11px, --surface2 bg, border, 4px radius, 1px 6px padding) · dot separator (3px, --border bg) · "Modified Xh ago" (11px mono, --text-muted) · word count
- [ ] **Editor body** (flex 1, overflowY auto, padding 8px 32px 32px):
  - TipTap WYSIWYG always-editable, no mode toggle
  - H1: 26px bold, letterSpacing -0.02em, marginBottom 20px
  - H2: 15px 600, marginTop 28px, marginBottom 8px
  - Body: 13.5px --text-secondary, lineHeight 1.7, marginBottom 12px
  - Task items: 14px checkbox (borderRadius 3px, 1.5px --border; done: --accent bg + ✓ in --bg text 9px) + text (13px, opacity 0.45 + strikethrough when done)
  - Auto-save on blur with 500ms debounce (no explicit save button needed, but keep Save in toolbar for explicit action)
- [ ] **Connections section** (borderTop --border, padding 16px 32px): 2-column grid (Outgoing / Backlinks)
  - Outgoing links: `LinkPill` (--surface2 bg, border, 4px radius, 3px 8px padding; entity icon + label 11.5px)
  - Backlinks: title (entity icon + label 11.5px) + excerpt (11px italic --text-muted)
  - Group label: 10px mono uppercase --text-muted
- [ ] **AI sidebar** (224px, padding 16px 0, overflowY auto):
  - **AI · Classification** header: mono uppercase 10px label + confidence badge (10px mono, --accent color, --accent-dim bg, 3px radius, 1px 5px pad)
  - Class result row: entity icon (11px) + type name (13px bold) + categories (11px mono --text-muted)
  - Divider (1px --border)
  - **Suggested tags**: tag chips (11px mono, border --border, 4px radius, 3px 7px); accepted state: --accent color + --accent-dim bg + --accent border; prefix "+" or "✓"
  - **Entity links found**: rows with entity icon (10px) + label (11.5px flex 1) + confidence % (10px mono --text-muted)
  - **Quick actions**: 4 buttons (Summarize / Extract tasks / Find related / Improve writing): 12px, border --border, 4px radius, 6px 10px padding, left-aligned text
  - All section titles: 10px mono uppercase --text-muted, padding 4px 16px 6px
  - Dividers at 8px 0
- [ ] **AI text selection toolbar**: floating above selection (from Phase 2.1)

### 3.4 Tasks Kanban redesign
**File:** `ui/src/views/Tasks.jsx` (wire-up already in Phase 1.1; this covers visual matching)

Already covered in Phase 1.1. Visual spec from design:
- [ ] Header: "Tasks" 17px fontWeight 700 letterSpacing -0.02em + right-aligned count badge + filter chips
- [ ] Board: `display: flex; gap: 0; flex: 1;` — columns are `flex: 1`, borderRight between them (no outer gap)
- [ ] Cards: background --surface, border --border, borderRadius 6px, padding 10px 12px, cursor grab, `userSelect: none`
- [ ] Project badge: 10px IBM Plex Mono, colored text + matching colored border, borderRadius 3px, 1px 5px padding
- [ ] Priority dot: 6×6px circle (--red / --yellow / --text-muted)
- [ ] Due date: 10px mono --text-muted
- [ ] Quick-add: --surface2 bg, 1px --accent border, 6px radius, 8px padding; confirm button: --accent bg, --bg text

### 3.5 Project Focus redesign
Already covered in Phase 1.3. Visual confirmations from design:
- [ ] Area badge: `font-family: var(--font-mono)`, pink ▲ icon + area name, 11px --text-muted
- [ ] Progress values: `font-family: var(--font-mono); font-size: 20px; font-weight: 700; letter-spacing: -0.03em`
- [ ] Progress track: height 3px, --surface2 bg, overflow hidden, border-radius 2px; fill: --accent, transition width 0.6s
- [ ] Complete button: --surface2 bg, border --border; done state: --green color + --green border
- [ ] Tab active: color --text, border-bottom 2px solid --accent
- [ ] Mini task cards in tasks tab: 11.5px --text-secondary title + 5×5px priority dot, --surface bg, border, 4px radius

### 3.6 Today / Dashboard redesign
**File:** `ui/src/views/Today.jsx` (replace `Dashboard.jsx` as the `/` default or make Today the landing)

Per design spec (`TodayView`):
- [ ] Date heading: `fontSize: 22, fontWeight: 700, letterSpacing: '-0.025em'`
- [ ] Summary line: mono, 12px, --text-muted ("X tasks due today · Y in progress")
- [ ] **Due Today** section: task rows (14px checkbox + title + project badge + priority dot), clicking navigates to task
- [ ] **Recently Modified** section: type icon (colored per entity system) + label + relative time, clicking navigates to entity

### 3.7 Command Palette redesign
**File:** `ui/src/components/search/CommandPalette.jsx`

Per design:
- [ ] Overlay: `rgba(0,0,0,0.55)`, centered at top (`paddingTop: 120`)
- [ ] Panel: 520px wide, --surface bg, border --border, borderRadius 10px, box-shadow `0 24px 64px rgba(0,0,0,0.7)`
- [ ] Input row: ⌕ (18px --text-muted) + input (15px --text, transparent bg, no outline) + "ESC" badge (10px mono, --surface2 bg, border, 3px radius, 1px 5px)
- [ ] Items: 13px --text-secondary + optional shortcut badge; hover: --surface2 bg; borderBottom --border-faint
- [ ] Empty state: 13px --text-muted centered

### 3.8 Capture modal redesign
**File:** `ui/src/components/capture/QuickCapture.jsx`

Per design (already covered in Phase 2.4 for functionality; this is the visual spec):
- [ ] Overlay: `rgba(0,0,0,0.55)`, centered
- [ ] Panel: 520px, --surface bg, border, borderRadius 10px, shadow `0 24px 64px rgba(0,0,0,0.7)`
- [ ] Header: "QUICK CAPTURE" uppercase mono 12px --text-muted (left) + type picker (right)
- [ ] Type chips: 10.5px mono, border, 4px radius, 2px 8px; active: --accent color + border + --accent-dim bg
- [ ] Textarea: transparent bg, no border/outline, resize none, 14px sans, lineHeight 1.65, padding 14px 16px, minHeight 120px
- [ ] Footer: "⌘↵ to save · ESC to cancel" (10px mono) + Save button (12px 600, --accent bg, --bg text, 5px radius, 5px 16px)

---

## Phase 4 — Store & API Field Name Migration

### 4.1 Migrate store from v1 aliases to v2 field names
**Files:** `ui/src/stores/useStore.js`, `ui/src/api/engram.js`, all view files

The backend serves v1 aliases (`name`, `raw_text`, `is_archived`) alongside v2 (`title`, `content`, `lifecycle`). The frontend only uses v1 names, blocking v2-only features.

- [ ] Update all API list/get responses to emit v2 field names (or update `to_dict()` to remove aliases after frontend migration)
- [ ] Update `useStore.js` data slices to use `title`, `content`, `lifecycle` (not `name`, `raw_text`)
- [ ] Update all view components that read `n.name`, `n.raw_text`, `p.name`, `p.color`
- [ ] Update `AppShell.jsx` sidebar pinned projects section (~line 115) to use v2 names
- [ ] Update `CommandPalette.jsx` search to use `title` not `name`

### 4.2 Expose `ai_status` in UI
**File:** all entity list/card components

- [ ] Show a spinning indicator on note/entity cards where `ai_status === 'processing'`
- [ ] After classification, show classification result + confidence inline on the entity card in lists
- [ ] Add polling or optimistic update: after capture, poll entity until `ai_status === 'done'`, then refresh the AI sidebar content

---

## Phase 5 — Polish & Completeness

### 5.1 Delete flow with cascade preview
**Vision:** "delete all linked objects with it, as long as they're not linked with anything else."
Backend `GET /api/v2/entities/:id/delete-preview` already exists.

- [ ] Before any entity deletion, call delete-preview endpoint
- [ ] Show modal: list of entities that would be orphaned with checkboxes (check = cascade delete)
- [ ] Pass `cascade=true/false` (or a list of IDs to cascade) to the delete API call

### 5.2 Follow-up date surfacing
- [ ] Show `follow_up_at` on entity cards when set (date in mono, --yellow if overdue)
- [ ] **Today view**: include any entities with `follow_up_at = today`, not just tasks with `due_date`
- [ ] Quick-set follow-up from entity detail sidebar: date input in the metadata section

### 5.3 Status transitions for all entity types
- [ ] Projects and Areas: status picker in detail header (Active / On Hold / Completed / Archived)
- [ ] Notes: lifecycle dropdown in AI sidebar (INBOX / PROJECT / AREA / RESOURCE / ARCHIVE)
- [ ] Project completion triggers rollup summary (existing `services/rollup.py`)
- [ ] Area archive: confirm modal, detaches child projects

### 5.4 MCP server alignment
**File:** `mcp_server/server.py`

- [ ] Audit all MCP tool handlers against v2 API paths
- [ ] Add MCP tools: `create_entity`, `search_entities`, `get_entity`, `update_entity`
- [ ] Test round-trip with Claude Desktop config
- [ ] Update `mcp_server/claude_desktop_config.json` if paths changed

### 5.5 Test coverage for closed loops
- [ ] Unit: `run_classify` creates `EntityTag` records (Phase 0.4)
- [ ] Unit: `callAiAction` sends to correct v2 URL with `selected_text` field (Phase 0.2)
- [ ] Unit: `TipTapEditor.onSave` passes `html` not `text` (Phase 0.1)
- [ ] Integration: full note create → classify → tag visible in AI sidebar
- [ ] Integration: task drag-and-drop updates status via `updateTask`
- [ ] Integration: delete preview modal → cascade delete
- [ ] Integration: AI selection popover → Extract Task → task appears in Tasks view

---

## Execution Order

| Week | Phase | Primary goal |
|------|-------|-------------|
| 1 | 0.1–0.5 | All current features work end-to-end |
| 2 | 1.1–1.4 | Core features complete (kanban, people, project progress) |
| 3 | 2.1–2.4 | AI loop fully closed (proposals, updates, reference capture) |
| 4 | 3.1–3.4 | Design system + Note view + Tasks view |
| 5 | 3.5–3.8 | Remaining views (Project, Today, Palette, Capture) |
| 6 | 4.1–4.2 | Store migration to v2 field names + ai_status |
| 7 | 5.1–5.5 | Delete cascade, follow-up, status, MCP, tests |

---

## What NOT to change

- **Backend architecture** — Entity/EntityLink/EntityTag model, async job queue, ai_pipeline stages
- **Routing structure** — The route map in `App.jsx` is sound; just fill in missing routes
- **Zustand store shape** — Keep the same store; only update field names in Phase 4
- **Flask blueprint structure** — Keep blueprints as-is; v2 prefix already applied
- **KanbanBoard.jsx** — Can be removed after Phase 1.1 (the Tasks view will use native HTML5 drag)
- **tweaks-panel.jsx** — This is a Claude Design tool only; do not bring into the React app

---

## Non-goals for V3

- Multi-user / sharing (single-user for now)
- Offline-first / sync (local server, always connected)
- PDF/file binary attachments (URL-based resources only)
- Mobile-native app (responsive web is sufficient)
