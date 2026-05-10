# Engram UI — SPEC.md

## 1. Concept & Vision

Engram is a **second brain for humans and AI agents alike** — a local-first, PARA-based knowledge management system with a web UI that finally feels as fluid as thinking. Capture anything in seconds, trust that it lands in the right place, and always see the full picture: what's connected, what's active, what needs attention.

The UI must feel like a **thinking environment**, not a database UI. Minimal chrome, maximum context. When you're in a project, nothing else exists. When you're capturing, nothing is in your way. When you're reviewing, the full web of connections is visible.

Design reference: Linear meets Roam Research — the spatial clarity and keyboard-first UX of Linear with the networked thought of Roam.

---

## 2. Design Language

### Color Palette
```
--bg-base:       #0D0D0F   (near-black canvas)
--bg-surface:   #16161A   (cards, panels)
--bg-elevated:   #1E1E24   (modals, dropdowns)
--bg-hover:      #25252E   (hover states)
--border:        #2A2A32   (subtle borders)
--border-focus:  #4A4A58   (focused borders)

--text-primary:  #EDEDEF   (main text)
--text-secondary:#8888A0   (secondary, labels)
--text-muted:    #55556A   (placeholders, disabled)

--accent:        #7C6AFF   (purple — primary actions, links)
--accent-warm:   #FF6B6B   (red — delete, archive, urgent)
--accent-green:  #4ADE80   (green — success, done)
--accent-amber:  #FBBF24   (amber — in-progress, warning)
--accent-blue:   #60A5FA   (blue — info, resources)

--bucket-inbox:  #7C6AFF
--bucket-resources:#FBBF24
--bucket-archives:#55556A
```

### Typography
- **Headings:** `"Inter"` (weight 600/700) — clean, legible, modern
- **Body:** `"Inter"` (weight 400/500)
- **Monospace:** `"JetBrains Mono"` — for note IDs, metadata, code
- Scale: 11 / 12 / 13 / 14 / 16 / 20 / 28 / 36px

### Spatial System
- Base unit: 4px
- Card padding: 16px
- Section gaps: 24px
- Sidebar width: 240px
- Max content width: 720px (note view), 1200px (dashboard)
- Border radius: 6px (small), 10px (cards), 14px (modals)

### Motion Philosophy
- Duration: 120ms (micro), 200ms (standard), 350ms (page)
- Easing: `cubic-bezier(0.16, 1, 0.3, 1)` — fast start, gentle land
- Principles: nothing animates without user intent; entrance animations are subtle and directional; no gratuitous motion

### Visual Assets
- Icons: **Lucide** (consistent 1.5px stroke, 16/18/20px sizes)
- No decorative imagery — content IS the visual
- Graph view: force-directed with D3.js or similar

---

## 3. Layout & Structure

### App Shell
```
┌──────────────────────────────────────────────────────┐
│  Sidebar (240px fixed)  │  Main Content Area         │
│  ─────────────────────  │  ─────────────────────────  │
│  [Logo / Quick Capture] │  [View Header + Actions]   │
│  [Nav Items]            │  [Content]                  │
│  ─────────────────────  │                             │
│  [Projects list]        │                             │
│  [Areas list]          │                             │
│  ─────────────────────  │                             │
│  [Person chips]        │                             │
│  ─────────────────────  │                             │
│  [Footer: search]      │                             │
└──────────────────────────────────────────────────────┘
```

### Views
1. **Dashboard** — Unified overview: inbox count, upcoming tasks, recent captures, active project cards with linked notes preview
2. **Inbox** — Raw capture queue, AI-suggested routing per note, bulk actions
3. **Notes** — Filterable by bucket/project/area/person, sortable by date
4. **Note Detail** — Full note content, linked entities, edit mode, AI suggestions panel
5. **Projects** — Card grid + focus mode (single project → all its notes, tasks, people)
6. **Areas** — Same as projects, but for ongoing responsibilities (not one-off deliverables)
7. **People** — Profile card per person, all notes/tasks linked to them
8. **Tasks** — Kanban board: Inbox → Open → In Progress → Done
9. **Graph** — Force-directed network of all notes, projects, areas, people, and their links
10. **Review** — Weekly review queue: inbox items needing triage, stale notes, upcoming deadlines
11. **Search** — Global full-text search with filters, results grouped by type

### Responsive Strategy
- Desktop-first (primary use case)
- Tablet: sidebar collapses to icon rail
- Mobile: bottom tab nav, sidebar becomes drawer

### Visual Pacing
- Dashboard: dense but organized — stat cards at top, then 2-column layout (recent + upcoming)
- Note detail: single-column, max 720px, generous vertical rhythm
- Graph: full-bleed canvas

---

## 4. Features & Interactions

### Quick Capture (Global)
- `Cmd/Ctrl + K` — opens command palette with capture mode
- Typing in command palette with `/` prefix triggers capture
- Can also type project references: `/ Henkanhacks` → creates note linked to Henkanhacks project
- Capture auto-classifies via API AI call and shows suggested bucket before confirming
- Escape to dismiss, Enter to save and stay open (for rapid capture), Cmd+Enter to save and close

### Command Palette (`Cmd/Ctrl + K`)
- Unified: search notes, jump to projects, create tasks, run commands
- Fuzzy search across all entities
- Recent items shown by default
- Keyboard-only navigable (arrows, enter, escape)
- Commands: `/capture`, `/search`, `/new-task`, `/goto:project:name`, `/review`

### Note Creation & Editing
- Click "+" in sidebar or `Cmd+N` → modal with bucket selector, project/area/person linker
- Raw text input with markdown support (bold, italic, code, links)
- AI suggestion panel: shows suggested bucket/project/area/person before save (calls API's `ai_meta`)
- Auto-links: `[[Project Name]]` or `@person` syntax creates links automatically
- Tags: inline `#tag` syntax parsed and saved as tag_ids
- Embed: paste URL → API call → auto-extracts title/site/meta and saves as linked note

### Note Card (List View)
```
┌─────────────────────────────────────────────────────────┐
│ [Bucket] [Project chip]              Mar 13 · 2:34pm   │
│                                                         │
│ Note preview text goes here, max 2 lines, truncated    │
│ with ellipsis if longer...                             │
│                                                         │
│ [#tag1] [#tag2]                    💬 3 · 📎 2 links   │
└─────────────────────────────────────────────────────────┘
```
- Hover: subtle elevation + quick actions appear (edit, delete, archive, link)
- Click: opens Note Detail
- Drag handle: drag to reorder or drag onto project/person chip to link

### Note Detail View
- Full raw_text rendered with markdown
- Sidebar panel: linked Project, Area, Person chips (clickable)
- Tags shown as removable pills
- AI suggestion panel: shows if note hasn't been classified / routed
- Edit button → inline editing mode (contenteditable)
- Archive / Delete in overflow menu

### Project Focus Mode
- Click project card → Focus Mode
- Header: project name, description, deadline, color, priority
- Tabs: **Notes** | **Tasks** | **People**
- Notes tab: all notes linked to this project
- Tasks tab: kanban for this project only
- People tab: all people linked via notes in this project
- Back arrow exits focus mode

### Task Kanban
- Columns: Inbox (unassigned) | Open | In Progress | Done
- Cards: task content, due date (if set), linked project/area
- Drag cards between columns → API call updates status
- Click card → edit inline (content, due date, priority)
- "+ Add Task" at bottom of each column
- Quick add: type and Enter (defaults to Open)

### Graph View
- Force-directed layout with D3.js
- Node types: Note (circle), Project (rounded rect), Area (diamond), Person (hexagon)
- Edge types: `links_to` (note→project/area/person), `parent_of` (project→task)
- Color: nodes colored by bucket
- Interactions: click node → sidebar shows detail, hover → highlights connections
- Controls: zoom, pan, filter by type, search to highlight

### Weekly Review
- Scoped to next 7 days / past 7 days
- Inbox queue: notes needing bucket assignment (show AI suggestion per note)
- Upcoming tasks: tasks with due dates in next 7 days
- Recent captures: notes from past 7 days grouped by bucket
- Stale items: notes older than 2 weeks with no modifications
- Bulk actions: select multiple → assign bucket / archive / link

### Search
- Global search bar in sidebar footer (always visible) + `Cmd+F`
- Results grouped: Notes | Projects | Areas | People | Tasks
- Filter chips: bucket, date range, has:links, has:tags
- Highlight matched terms in results
- Click result → opens detail view

### Keyboard Shortcuts
| Shortcut | Action |
|---|---|
| `Cmd+K` | Command palette |
| `Cmd+N` | New note |
| `Cmd+F` | Focus search |
| `Cmd+S` | Save current edit |
| `Escape` | Close modal / cancel |
| `J / K` | Navigate down / up (in lists) |
| `O` | Open selected item |
| `E` | Edit selected item |
| `Backspace` | Delete (with confirmation) |
| `Cmd+Enter` | Submit / save in modal |

---

## 5. Component Inventory

### Sidebar
- Logo + quick capture button at top
- Nav items with Lucide icons, active state (accent left border + bg)
- Projects section (collapsible, shows up to 8, then "See all")
- Areas section (same)
- People chips row (scrollable, +N more)
- Search bar at bottom
- States: expanded (240px), icon rail (56px), hidden (mobile)

### Note Card
- States: default, hover (elevated + quick actions), selected (accent border), dragging (opacity 0.5 + shadow)
- Quick actions on hover: link, archive, delete (icon buttons)
- Bucket badge: colored pill (Inbox=purple, Projects=green, Areas=blue, Resources=amber, Archives=gray)

### Command Palette
- Modal overlay (centered, max 600px wide, max 70vh)
- Input at top with search icon
- Results list below with type icons + labels
- Keyboard selection highlight
- Section headers for grouped results
- Loading state: spinner in input

### Task Card
- Compact (kanban): title, due badge (red if overdue, amber if today, gray otherwise), priority dot
- Expanded: full content, linked entities, edit/delete actions
- Dragging state: slight rotation, drop shadow

### Modal
- Centered, backdrop blur
- Max widths: sm (400px), md (560px), lg (720px)
- Header with title + close button
- Scrollable body
- Footer with action buttons (Cancel secondary, Save primary)

### Bucket Badge
- Small pill: colored dot + label
- Colors per bucket (see palette)

### Project/Person/Area Chip
- Small pill with icon + label
- Clickable → navigates to that entity
- `×` button to unlink

### Toast Notifications
- Bottom-right stack
- Types: success (green), error (red), info (blue), warning (amber)
- Auto-dismiss after 3s (success) or 5s (error)
- Slide-in animation from right

### Empty States
- Centered illustration (simple SVG), heading, subtext, CTA button
- Per-view: "No notes yet" / "No projects yet" / "Inbox is clear"

---

## 6. Technical Approach

### Stack
- **Frontend:** React 18 + Vite
- **Routing:** React Router v6
- **State:** Zustand (lightweight, minimal boilerplate)
- **Styling:** CSS Modules (no Tailwind) — matches design language precisely
- **Graph:** D3.js (force simulation)
- **HTTP:** native `fetch` (no axios needed)
- **Icons:** Lucide React
- **Markdown:** `react-markdown` + `remark-gfm`

### Project Structure
```
frontend/
├── public/
│   └── vite.svg
├── src/
│   ├── main.jsx
│   ├── App.jsx
│   ├── index.css          (CSS variables, resets, global styles)
│   ├── api/
│   │   └── engram.js      (all API calls — single source of truth)
│   ├── stores/
│   │   └── useStore.js    (Zustand store: notes, projects, ui state)
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.jsx
│   │   │   ├── Sidebar.module.css
│   │   │   ├── AppShell.jsx
│   │   │   └── AppShell.module.css
│   │   ├── notes/
│   │   │   ├── NoteCard.jsx
│   │   │   ├── NoteDetail.jsx
│   │   │   ├── NoteEditor.jsx
│   │   │   └── NoteList.jsx
│   │   ├── projects/
│   │   │   ├── ProjectCard.jsx
│   │   │   └── ProjectFocus.jsx
│   │   ├── tasks/
│   │   │   ├── TaskBoard.jsx
│   │   │   ├── TaskColumn.jsx
│   │   │   └── TaskCard.jsx
│   │   ├── graph/
│   │   │   └── GraphView.jsx
│   │   ├── search/
│   │   │   ├── CommandPalette.jsx
│   │   │   └── SearchBar.jsx
│   │   └── ui/
│   │       ├── Modal.jsx
│   │       ├── Toast.jsx
│   │       ├── Badge.jsx
│   │       └── EmptyState.jsx
│   └── views/
│       ├── Dashboard.jsx
│       ├── Inbox.jsx
│       ├── Notes.jsx
│       ├── NoteDetailView.jsx
│       ├── Projects.jsx
│       ├── Areas.jsx
│       ├── People.jsx
│       ├── Tasks.jsx
│       ├── Graph.jsx
│       ├── Review.jsx
│       └── Search.jsx
├── index.html
├── vite.config.js
├── package.json
└── .env               (VITE_API_BASE=http://localhost:5001)
```

### API Integration
- All API calls through `src/api/engram.js`
- Base URL from `import.meta.env.VITE_API_BASE`
- Endpoints (existing, tested via curl):

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/notes` | List notes (params: `?bucket=&limit=&offset=`) |
| POST | `/api/v1/notes` | Create note (`{raw_text, bucket, project_id, ...}`) |
| GET | `/api/v1/notes/:id` | Get note detail |
| PUT | `/api/v1/notes/:id` | Update note |
| DELETE | `/api/v1/notes/:id` | Delete note |
| GET | `/api/v1/notes/search?q=` | Full-text search |
| GET | `/api/v1/projects` | List projects |
| POST | `/api/v1/projects` | Create project |
| GET | `/api/v1/projects/:id` | Get project with notes/tasks count |
| PUT | `/api/v1/projects/:id` | Update project |
| GET | `/api/v1/areas` | List areas |
| POST | `/api/v1/areas` | Create area |
| GET | `/api/v1/people` | List people |
| POST | `/api/v1/people` | Create person |
| GET | `/api/v1/tasks` | List tasks |
| POST | `/api/v1/tasks` | Create task |
| PUT | `/api/v1/tasks/:id` | Update task |
| GET | `/api/v1/tags` | List tags |

### Flask Integration
- New route in `app.py`:
  ```python
  @app.route('/new')
  def serve_react_app():
      return send_from_directory('static-new', 'index.html')
  ```
- Vite build output: `frontend/dist/` → copied to `engram/static-new/`
- API calls proxied through Flask if needed for CORS

### Authentication
- None for now (local-first, localhost only)
- Auth is a future concern (see SPEC.md auth section)

### Performance
- Notes list: virtualized with `react-window` if >100 items
- Graph: canvas-based rendering for >500 nodes
- Debounced search (300ms)
- Optimistic UI updates on mutations (update local state before API confirms)

---

## 7. Phased Build Plan

### Phase 1 — Foundation (this session)
- [ ] Project scaffold: Vite + React, routing, CSS variables
- [ ] AppShell + Sidebar layout
- [ ] API client module (`src/api/engram.js`)
- [ ] Zustand store skeleton
- [ ] Dashboard view
- [ ] Basic Notes list + NoteCard

### Phase 2 — Core CRUD
- [ ] Note creation modal with AI suggestions
- [ ] Note detail view + edit
- [ ] Projects view + ProjectFocus mode
- [ ] People view
- [ ] Areas view

### Phase 3 — Interactive Features
- [ ] Command palette (`Cmd+K`)
- [ ] Task kanban board
- [ ] Drag-and-drop linking
- [ ] Inbox + review queue

### Phase 4 — Visualization
- [ ] Graph view (D3)
- [ ] Search with filters
- [ ] Weekly review dashboard

### Phase 5 — Polish
- [ ] Keyboard shortcuts
- [ ] Toast notifications
- [ ] Mobile responsiveness
- [ ] Empty states
- [ ] Loading skeletons

---

## 8. Open Questions (to resolve during build)

1. ⚠️ **Flask static serving**: How does the Flask app currently serve static files? Need to inspect `app.py` to add `/new` route.
2. ⚠️ **Build destination**: Frontend builds to `frontend/dist/` — should this replace `static/` or live as `static-new/`?
3. ⚠️ **AI auto-classification**: Is the AI bucket suggestion happening server-side in Flask? What's the API payload for note creation?
4. ⚠️ **Tags**: API has `/tags` endpoint but tag creation/update isn't documented. How are tag_ids applied to notes?
5. ⚠️ **Task fields**: What fields does a task have beyond `content`? `status`, `due_date`, `project_id`?
6. ⚠️ **Note update**: Does `PUT /api/v1/notes/:id` accept `{bucket, project_id, area_id, person_id}` or only `{raw_text}`?
7. ⚠️ **MCP integration**: Should MCP server be added to this project as part of the UI work, or separate?
