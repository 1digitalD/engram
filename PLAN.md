# Engram — Full Implementation Plan
> Multi-phase, multi-iteration build plan covering backend schema, architecture, services, and frontend.  
> Each workstream within a phase is independently assignable to a parallel Cursor agent.  
> File ownership map at the bottom prevents merge conflicts.

---

## Architecture Vision

Engram evolves from a basic note-capture tool into a **Second Brain** with an **agentic intelligence layer**:

```
Phase 1 — Foundation       Fix broken things, core schema, inline editing, daily notes
Phase 2 — Relational Depth  M2M relationships, typed resources, rich people model
Phase 3 — Intelligence      AI agents: summarization, link proposals, pattern detection
Phase 4 — Review & Health   Weekly review UX, PKM health metrics, project→area rollup
Phase 5 — Advanced UX       Graph overhaul, Maps of Content, templates, keyboard-first
```

Phases 1–2 are sequential (2 depends on 1 schema). Phases 3–5 run in parallel after Phase 2 stabilizes.

---

---

# PHASE 1 — Foundation & Fixes
> Goal: Eliminate all broken functionality, add core schema relationships, make the note-taking flow friction-free.  
> Workstreams: 6 parallel agents. No inter-WS dependencies except WS5/WS6 needing WS3's store changes.

---

## P1-WS1 — Backend: Core Schema, API & Services
**Files:** `models.py`, `api/projects.py`, `api/tasks.py`, `api/areas.py`, `api/notes.py`, `services/extractor.py`, new `api/daily.py`, new `migrations/004_*.py`

### Iteration A — Schema changes

**Add `area_id` to Project** (`models.py` Project class):
```python
area_id = Column(String(36), ForeignKey("areas.id"), nullable=True)
area = relationship("Area", back_populates="projects")
```

**Add `area_id` and `note_id` to Task** (`models.py` Task class):
```python
area_id = Column(String(36), ForeignKey("areas.id"), nullable=True)
note_id = Column(String(36), ForeignKey("notes.id"), nullable=True)
area    = relationship("Area", back_populates="tasks")
source_note = relationship("Note", back_populates="tasks", foreign_keys="[Task.note_id]")
```

**Add reverse relationships** to Area:
```python
projects = relationship("Project", back_populates="area", lazy="dynamic")
tasks    = relationship("Task",    back_populates="area", lazy="dynamic")
```

**Add reverse to Note:**
```python
tasks = relationship("Task", back_populates="source_note", foreign_keys="[Task.note_id]")
```

**Migration script** `migrations/004_add_area_project_task_fields.py`:
```python
def upgrade():
    # ALTER TABLE projects ADD COLUMN area_id VARCHAR(36) REFERENCES areas(id)
    # ALTER TABLE tasks    ADD COLUMN area_id VARCHAR(36) REFERENCES areas(id)
    # ALTER TABLE tasks    ADD COLUMN note_id VARCHAR(36) REFERENCES notes(id)
```
Run: `python migrations/004_add_area_project_task_fields.py`

### Iteration B — API serialization updates

Update `to_dict()` on Project to include `area_id`, `area_name`.  
Update `to_dict()` on Task to include `area_id`, `area_name`, `note_id`.  
Update `to_dict()` on Area to include `project_count`, `task_count`.  

Update `GET /api/v1/projects` to accept `?area_id=` filter.  
Update `GET /api/v1/tasks` to accept `?area_id=` and `?note_id=` filters.  
Update `POST` and `PATCH` for projects and tasks to accept and persist new fields.

Update `Note.to_dict()` to include `task_count` (count of tasks with `note_id == note.id`).

### Iteration C — Daily Notes API

New file `api/daily.py`, registered as blueprint `/api/v1/daily`:

```
GET  /api/v1/daily?date=YYYY-MM-DD
     → Returns daily note for date; auto-creates if none exists.
     Auto-created template:
       # Daily — {date}
       ## Focus
       ## Notes
       ## Tasks

POST /api/v1/daily/append
     Body: { "content": "...", "date": "YYYY-MM-DD" }
     → Appends a paragraph block to the ## Notes section of the daily note.
     Returns updated note.
```

Detection: notes where `raw_text` starts with `# Daily — ` and bucket is INBOX.  
On GET, if none found for date, auto-create and return.

### Iteration D — Inline Task Extraction Service

In `services/extractor.py`, add `extract_inline_tasks(note_id, raw_text, project_id, area_id)`:
- Parse lines matching `- [ ] text` and `- [x] text`
- Upsert Task records keyed by `(note_id, title_hash)`:
  - `[ ]` → PENDING, `[x]` → DONE
  - Lines removed since last save → CANCELLED
- Returns list of created/updated task dicts

Call from `api/notes.py` PATCH handler when `raw_text` changes.  
Call from `api/ingest.py` after note creation.

---

## P1-WS2 — Note Cards: Markdown, Display & Interaction
**Files:** `ui/src/components/notes/NoteCard.jsx`, `NoteCard.module.css`, `ui/src/index.css`

### Iteration A — Render markdown, not raw text
Replace raw text `<p>` with `<ReactMarkdown remarkPlugins={[remarkGfm]}>` truncated at 400 chars.  
Disable heading anchors in cards (h1/h2/h3 → `<strong>`). Open links in new tab.

### Iteration B — Syntax highlighting
Install `react-syntax-highlighter`. Add custom `code` renderer using Prism `oneDark` theme.  
Apply in NoteCard and NoteDetailView.

### Iteration C — Expandable cards
Add `expanded` local state. Collapsed = 400-char preview. Expanded = full content.  
Expand toggle button in card footer. Expanded cards: `max-height: none`, subtle top accent border.

### Iteration D — Demote AI badge
Move `AI 90%` badge to `opacity: 0`, revealed only on `.card:hover`.  
Remove the expand dropdown arrow — AI detail lives in note detail view only.

### Iteration E — Clickable tag filter
Tags on cards navigate to `/notes?tag={name}` on click.  
`e.stopPropagation()` to prevent card navigation on tag click.

### Iteration F — Fix `.spin` CSS
Add to `index.css`:
```css
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.spin { animation: spin 0.8s linear infinite; }
```

### Iteration G — Strip import metadata
If `note.raw_text` starts with `"Imported from"` and contains `"Source Notion ID"`, show empty preview (not the raw metadata string). Display a muted "Imported note — click to view" placeholder.

---

## P1-WS3 — CRUD Completeness & Store Fixes
**Files:** `ui/src/stores/useStore.js`, `ui/src/components/search/CommandPalette.jsx`, `ui/src/views/Tasks.jsx`, `ui/src/views/Tasks.module.css`, `ui/src/views/Areas.jsx`, `ui/src/views/People.jsx`  
**Owns `useStore.js`** — no other WS should modify it in Phase 1.

### Iteration A — Missing store actions
Add to `useStore.js`:
- `updateArea(id, updates)` / `deleteArea(id)` — matches Projects pattern
- `updatePerson(id, updates)` / `deletePerson(id)`
- `captureOpen: false`, `openCapture()`, `closeCapture()` — for floating quick-capture

Update `createTask` and `updateTask` to pass through `due_date`, `area_id`, `note_id`.

### Iteration B — Area & Person edit UI
`AreaFocus.jsx`: pencil edit button in header → Modal with Name, Description, Color fields.  
Delete button with confirmation → `deleteArea()` → navigate to `/areas`.  
`Areas.jsx`: add delete to area cards.  
`People.jsx`: edit modal per person (Name, Email, Notes textarea, Last Contacted date input). Delete with confirmation.

### Iteration C — Fix CommandPalette navigation
`CommandPalette.jsx` line ~64:
- `case 'area'`: navigate to `/areas/${item.id}` (not `/areas`)
- "Capture note" quick action: call `useStore.getState().openCapture()` instead of navigating to `/notes`

### Iteration D — Task improvements
`Tasks.jsx`: click task title → inline editable `<input>`, Enter/blur saves via `updateTask`.  
Add `<input type="date">` to task creation modal for `due_date`.  
Pass `due_date: value || null` in `createTask` call.

---

## P1-WS4 — Note Detail & Inline Editing
**Files:** `ui/src/views/NoteDetailView.jsx`, `NoteDetailView.module.css`, `ui/src/components/notes/NoteEditor.jsx`, `NoteEditor.module.css`, `ui/src/views/Inbox.jsx`, `Inbox.module.css`, new route `ui/src/views/Today.jsx`

### Iteration A — Click-to-edit inline in NoteDetailView
Replace Edit button → modal with in-place editing:  
Click note content → textarea appears with `autoFocus`, full content editable.  
`⌘Enter` or Save button → `updateNote(id, { raw_text })`. Esc → cancel, restore original.  
Subtle "Click to edit" hint on hover.

### Iteration B — Split Write/Preview in NoteEditor
Add tab bar: "Write" | "Preview" to NoteEditor modal.  
Preview tab renders full `<ReactMarkdown>` of current textarea content.  
Side-by-side on screens > 768px; stacked on mobile.

### Iteration C — Backlinks panel in NoteDetailView
Below note content, fetch `linksAPI.forNote(note.id)` on mount.  
Display incoming + outgoing links as clickable note excerpts.  
"+ Link a note" button → inline search (reuses CommandPalette search logic) → `linksAPI.create(src, dst, type)`.

### Iteration D — Tasks panel in NoteDetailView
Below backlinks, show `tasks.filter(t => t.note_id === note.id)`.  
"+ Add task" inline form: title input, Enter creates task with `note_id` pre-filled.  
Task rows have checkbox (toggles status PENDING↔DONE) and delete.

### Iteration E — AI suggestion panel in Inbox
Each Inbox item shows AI suggestion before routing buttons:  
`note.ai_meta.bucket`, `note.ai_meta.suggested_project`, first 120 chars of `note.ai_meta.reasoning`.  
"Use suggestion" one-click button applies AI's recommended bucket/project/area.

### Iteration F — Today view (`/today`)
New `views/Today.jsx`. Route `/today` added to `App.jsx`.  
On mount: `GET /api/v1/daily?date={today}` → loads or creates today's note.  
Renders in inline-edit mode by default.  
Right column: today's tasks (due_date == today) + active project summaries.  
Add "Today" to AppShell sidebar nav between Dashboard and Inbox.

---

## P1-WS5 — Navigation & Layout Polish
**Files:** `ui/src/components/layout/AppShell.jsx`, `AppShell.module.css`, `ui/src/views/AreaFocus.jsx`, `ui/src/views/ProjectFocus.jsx`, `ui/src/views/Graph.jsx`, `Graph.module.css`  
**Reads** `captureOpen`/`closeCapture` from store — merge WS3 first or stub with local state.

### Iteration A — Sidebar restructure
Move Search to top of sidebar (below Capture button). Remove `margin-top: auto` hack.  
Add "AREAS" quicklinks section below PROJECTS (top 5 areas with color dot).  
Add `title={name}` tooltip on all truncated quicklink names.

### Iteration B — Entity header redesign
Replace unexplained color dot with 4px left border in entity color:  
`style={{ borderLeft: '4px solid {entity.color || var(--accent)}' }}` on entity headers.  
`AreaFocus.jsx` and `ProjectFocus.jsx`.

### Iteration C — Strip import metadata from headers
Filter `description` in `AreaFocus.jsx` and `ProjectFocus.jsx`:  
```js
const clean = (d) => d?.startsWith('Imported from') && d?.includes('Source Notion ID') ? null : d;
```
Show nothing when description is import metadata.

### Iteration D — AreaFocus: add Projects & Tasks tabs
Add tab bar to `AreaFocus.jsx` matching `ProjectFocus.jsx` pattern:  
- Notes tab (existing)  
- Projects tab: grid of `projects.filter(p => p.area_id === area.id)` (requires P1-WS1)  
- Tasks tab: list of `tasks.filter(t => t.area_id === area.id)` (requires P1-WS1)  
Show empty state with explanatory text until P1-WS1 is merged.

### Iteration E — ProjectFocus: show parent area breadcrumb
In project header: `{project.area_name && <NavLink to={/areas/${project.area_id}}>↖ {project.area_name}</NavLink>}`

### Iteration F — Graph: Open node action
Node detail panel gets "Open →" button navigating to the entity's route.  
Move "Relationship graph" button from orphaned position to entity header action row. Relabel "Graph view".

---

## P1-WS6 — Power Features
**Files:** `ui/src/App.jsx`, `ui/src/views/Notes.jsx`, new `ui/src/components/notes/QuickCapture.jsx`, new `QuickCapture.module.css`  
**Depends on** WS3 iteration A (`openCapture` store action).

### Iteration A — Floating QuickCapture overlay
`QuickCapture.jsx`: fixed bottom-right corner, 480px wide, slides up from bottom.  
Full-height textarea (markdown). `⌘Enter` saves via `ingestAPI.capture()`. Esc dismisses.  
Auto-saves draft to `localStorage` on every keystroke.  
Rendered in `App.jsx` outside the router — persists across all routes.  
`AppShell.jsx` binds `captureOpen` store state to `<QuickCapture isOpen={captureOpen} />`.

### Iteration B — Interactive task checkboxes
Custom ReactMarkdown `listItem` renderer in `NoteDetailView` and `NoteCard`:  
`- [ ]` → unchecked HTML checkbox. `- [x]` → checked.  
onChange: toggle `[ ]`↔`[x]` in `raw_text` and call `updateNote`. 

### Iteration C — Keyboard navigation
Global `keydown` listener in `App.jsx` (guard: skip if input/textarea focused):  
`i` → `/inbox`, `t` → `/tasks`, `G` (shift+g) → `/graph`, `?` → keyboard help modal.  
In note list views: `j/k` navigate notes, `Enter` open, `Esc` back.

### Iteration D — Tag filter in Notes view
`Notes.jsx` reads `?tag=` from `useSearchParams()`.  
Dismissible filter chip when tag active. Tags on cards (WS2-E) route here.

### Iteration E — Keyboard help modal
`?` key opens `KeyboardHelp` component: table of all shortcuts.  
Dismiss with Esc or click outside.

---

## Phase 1 — File Ownership Map

| File | Owner |
|------|-------|
| `models.py` | P1-WS1 |
| `api/projects.py`, `api/tasks.py`, `api/areas.py`, `api/notes.py` | P1-WS1 |
| `services/extractor.py`, `api/daily.py` *(new)* | P1-WS1 |
| `migrations/004_*.py` *(new)* | P1-WS1 |
| `ui/src/stores/useStore.js` | P1-WS3 |
| `ui/src/components/search/CommandPalette.jsx` | P1-WS3 |
| `ui/src/views/Tasks.jsx`, `Tasks.module.css` | P1-WS3 |
| `ui/src/views/Areas.jsx`, `People.jsx` | P1-WS3 |
| `ui/src/components/notes/NoteCard.jsx`, `NoteCard.module.css` | P1-WS2 |
| `ui/src/index.css` | P1-WS2 |
| `ui/src/views/NoteDetailView.jsx`, `NoteDetailView.module.css` | P1-WS4 |
| `ui/src/components/notes/NoteEditor.jsx`, `NoteEditor.module.css` | P1-WS4 |
| `ui/src/views/Inbox.jsx`, `Inbox.module.css` | P1-WS4 |
| `ui/src/views/Today.jsx` *(new)* | P1-WS4 |
| `ui/src/components/layout/AppShell.jsx`, `AppShell.module.css` | P1-WS5 |
| `ui/src/views/AreaFocus.jsx`, `ProjectFocus.jsx` | P1-WS5 |
| `ui/src/views/Graph.jsx`, `Graph.module.css` | P1-WS5 |
| `ui/src/App.jsx` | P1-WS6 |
| `ui/src/views/Notes.jsx`, `Notes.module.css` | P1-WS6 |
| `ui/src/components/notes/QuickCapture.jsx` *(new)* | P1-WS6 |

## Phase 1 — Merge Order
1. P1-WS1 + P1-WS2 + P1-WS3 simultaneously (no shared files)
2. P1-WS4 (reads store, does not write)
3. P1-WS5 (reads `captureOpen` from WS3 — merge WS3 first)
4. P1-WS6 (needs `openCapture` from WS3)

---

---

# PHASE 2 — Relational Depth
> Goal: Complete the PKM relationship model. Notes belong to multiple projects. Resources become typed entities. People become rich relationship nodes. Projects roll up into Areas properly.  
> Prerequisite: Phase 1 fully merged.

---

## P2-WS1 — M2M Notes ↔ Projects
**Files:** `models.py`, `api/notes.py`, `api/projects.py`, new `migrations/005_*.py`, `ui/src/stores/useStore.js`, `ui/src/components/notes/NoteEditor.jsx`, `ui/src/views/ProjectFocus.jsx`

### Iteration A — Schema: note_projects join table
```python
note_projects = Table(
    "note_projects",
    db.Model.metadata,
    Column("note_id",    String(36), ForeignKey("notes.id"),    primary_key=True),
    Column("project_id", String(36), ForeignKey("projects.id"), primary_key=True),
)
```

Migrate `Note.project_id` (single FK) → M2M relationship:
- Keep `project_id` column for backward compatibility (set to first project in list)
- Add `projects` M2M relationship alongside the existing scalar `project` relationship
- Migration: for all notes with `project_id` set, insert a row into `note_projects`

**Migration `005_note_projects_m2m.py`:**
```sql
CREATE TABLE note_projects (
    note_id    VARCHAR(36) REFERENCES notes(id)    ON DELETE CASCADE,
    project_id VARCHAR(36) REFERENCES projects(id) ON DELETE CASCADE,
    PRIMARY KEY (note_id, project_id)
);
INSERT INTO note_projects (note_id, project_id)
SELECT id, project_id FROM notes WHERE project_id IS NOT NULL;
```

### Iteration B — API updates
`POST /api/v1/notes` and `PATCH /api/v1/notes/<id>`: accept `project_ids: [...]` array.  
`GET /api/v1/notes`: serialize `project_ids` and `projects` arrays.  
Maintain backward compat: if `project_id` (scalar) sent, treat as `project_ids: [project_id]`.  
`GET /api/v1/projects/<id>/notes`: unchanged (uses join table).

### Iteration C — UI: multi-project assignment
`NoteEditor.jsx`: replace single Project `<select>` with multi-select chips:  
Type to search projects → select → adds as chip. Click chip × to remove.  
`NoteDetailView.jsx`: project chips in metadata row, each linkable, removable.  
`ProjectFocus.jsx` notes tab: unchanged (filters by project_id in join table).

---

## P2-WS2 — Typed Resources
**Files:** new `models.py` additions, new `api/resources.py`, new `migrations/006_*.py`, new `ui/src/views/Resources.jsx`, `Resources.module.css`, `ui/src/views/ResourceDetail.jsx`, `ui/src/components/layout/AppShell.jsx`

### Iteration A — Schema: Resource model and subtypes
```python
class ResourceType(PyEnum):
    ARTICLE = "ARTICLE"
    BOOK    = "BOOK"
    URL     = "URL"
    VIDEO   = "VIDEO"
    PAPER   = "PAPER"
    TOOL    = "TOOL"
    OTHER   = "OTHER"

class Resource(BaseModel):
    __tablename__ = "resources"
    title        = Column(String(500), nullable=False)
    resource_type = Column(Enum(ResourceType), default=ResourceType.OTHER)
    url          = Column(String(2000), nullable=True)
    author       = Column(String(255), nullable=True)
    published_at = Column(DateTime, nullable=True)
    description  = Column(Text, nullable=True)
    my_notes     = Column(Text, nullable=True)   # personal annotations (markdown)
    is_read      = Column(Boolean, default=False)
    rating       = Column(Integer, nullable=True)  # 1-5
    area_id      = Column(String(36), ForeignKey("areas.id"), nullable=True)
    area         = relationship("Area", back_populates="resources")
    tags         = relationship("Tag", secondary="resource_tags", back_populates="resources")
```

Association: `resource_tags` (resource_id, tag_id).  
Add `resources = relationship("Resource", ...)` to `Area`.  
Migration `006_resources.py`: create `resources` and `resource_tags` tables.

### Iteration B — API: full CRUD
New `api/resources.py` blueprint at `/api/v1/resources`:  
`GET /resources?type=BOOK&area_id=&tag=&unread=true`  
`POST /resources` with all fields  
`PATCH /resources/<id>`  
`DELETE /resources/<id>`  
`GET /resources/<id>/notes` — notes that reference this resource  

Ingestion: if `ingest` source is a URL, auto-create Resource instead of Note (detect via `source` field).

### Iteration C — UI: Resources view
New route `/resources` in AppShell (add to nav after People).  
`Resources.jsx`: grouped by type (Books, Articles, URLs, etc.). Tabs or type pills.  
Card per resource: title, author, type badge, read/unread indicator, star rating, area tag.  
`ResourceDetail.jsx`: full page with metadata, personal notes (markdown editor), linked notes, tags.  
"Add Resource" modal: URL auto-fetches title/description via Open Graph (backend fetch).

### Iteration D — Link notes to resources
`Note.resource_id` FK (nullable) — a note can reference a resource (e.g., highlights from a book).  
In `NoteDetailView`: "Source" field — link to parent resource if set.  
In `ResourceDetail`: "Notes & Highlights" section shows all linked notes.

---

## P2-WS3 — Rich People Model
**Files:** `models.py` (Person), `api/people.py`, new `migrations/007_*.py`, `ui/src/views/People.jsx`, new `ui/src/views/PersonDetail.jsx`

### Iteration A — Schema: Person enrichment
Add to `Person`:
```python
role        = Column(String(255), nullable=True)
company     = Column(String(255), nullable=True)
tags        = relationship("Tag", secondary="person_tags", ...)
area_id     = Column(String(36), ForeignKey("areas.id"), nullable=True)
area        = relationship("Area", back_populates="people")
# Interaction log stored as JSON array of {date, summary, note_id}
interactions = Column(JSON, nullable=True, default=list)
```

Migration `007_person_enrichment.py`: add `role`, `company`, `area_id` columns to `people`.  
Add `person_tags` association table.

### Iteration B — API updates
`GET /api/v1/people`: include `role`, `company`, `area_id`, `note_count`, `last_contacted_at`.  
`POST /api/v1/people/<id>/interaction`: log a timestamped interaction summary (updates `last_contacted_at`).  
`GET /api/v1/people/<id>`: full detail with notes, interaction history, tags.

### Iteration C — UI: PersonDetail view
New route `/people/:id` → `PersonDetail.jsx` (currently only `/people` list exists).  
Sections: Profile (name, role, company, email, area), Interaction History, Notes, Tags.  
"Log interaction" inline: quick textarea → saves interaction to JSON log + updates `last_contacted_at`.  
`People.jsx` cards: add Role, Company, note count. Cards link to `/people/:id`.  
`CommandPalette.jsx`: person selection navigates to `/people/${id}` (currently broken same as areas).

---

## P2-WS4 — Area ↔ Project Hierarchy UI
**Files:** `ui/src/views/Areas.jsx`, `ui/src/views/AreaFocus.jsx`, `ui/src/views/Projects.jsx`, `ui/src/views/ProjectFocus.jsx`, `ui/src/components/notes/NoteEditor.jsx`

### Iteration A — Area grid shows nested projects
`Areas.jsx` area cards: show project count badge. On expand (or in detail), list nested projects.  
Project cards in `Projects.jsx`: show parent area name as breadcrumb chip. Click → area detail.

### Iteration B — Project creation: area assignment
`Projects.jsx` creation modal: add "Area" dropdown. New projects can be assigned to an area at creation.  
NoteEditor: when project selected, auto-populate area from that project's area (can override).

### Iteration C — Area completion flow
When all projects under an area are archived, surface a banner:  
"All projects in {Area} are complete. Archive this area or add new projects."  
Archive area: moves area and all its notes to ARCHIVES bucket.

### Iteration D — PARA breadcrumb trail
In NoteDetailView metadata row, show full hierarchy:  
`Area → Project → Note`  
Each level is a clickable link. This makes the PARA structure navigable from any note.

---

---

# PHASE 3 — Intelligence Layer
> Goal: Add proactive AI agents that enrich the knowledge base automatically. The system observes patterns, proposes links, summarizes content progressively, and detects emerging structure.  
> Prerequisite: Phase 2 fully merged.

---

## P3-WS1 — Progressive Summarization Agent
**Files:** new `services/summarizer.py`, new `api/summarize.py`, `models.py` (extend WeeklySummary), `ui/src/views/Review.jsx`, `Review.module.css`

### Iteration A — Layered summary model
Extend `WeeklySummary` to support multiple granularities:
```python
class SummaryGranularity(PyEnum):
    DAILY   = "DAILY"
    WEEKLY  = "WEEKLY"
    MONTHLY = "MONTHLY"

# Add to WeeklySummary (rename to Summary):
granularity  = Column(Enum(SummaryGranularity), default=SummaryGranularity.WEEKLY)
date_from    = Column(DateTime, nullable=False)
date_to      = Column(DateTime, nullable=False)
key_themes   = Column(JSON, nullable=True)    # ["theme1", "theme2"]
action_items = Column(JSON, nullable=True)    # extracted action items
```

Migration: add `granularity`, `date_from`, `date_to`, `key_themes`, `action_items` to `weekly_summaries`.

### Iteration B — Summarization service
`services/summarizer.py`:
- `summarize_notes(notes: list[Note], granularity: str, entity_name: str) -> dict`
  - Calls Claude claude-sonnet-4-6 with note content
  - Returns `{ summary, key_themes, action_items, token_count }`
- `run_daily_summary(date: date)` — summarizes all notes from that day per project/area
- `run_weekly_rollup(week: int, year: int)` — synthesizes daily summaries into weekly
- `run_monthly_rollup(month: int, year: int)` — synthesizes weekly summaries into monthly

Use prompt caching (Anthropic SDK `cache_control`) for system prompt and entity context.

### Iteration C — Scheduled background jobs
New `services/scheduler.py` using APScheduler or a simple cron via Flask CLI commands:
```
flask summarize daily   # run nightly at 11pm
flask summarize weekly  # run Sunday at 11pm
flask summarize monthly # run last day of month at 11pm
```

Manual trigger: `POST /api/v1/summarize` body `{ entity_type, entity_id, granularity }`.

### Iteration D — Review view overhaul
`Review.jsx`: replace static layout with layered summary display.  
Tabs: Daily | Weekly | Monthly.  
Each tab shows: summary text, key themes as tags, action items as checkable tasks, note count.  
"Generate now" button triggers on-demand summarization for selected entity + period.  
Entity selector (project / area) to view summary for specific context.

---

## P3-WS2 — AI Link Proposal Service
**Files:** new `services/link_proposals.py`, new `api/proposals.py`, `ui/src/views/NoteDetailView.jsx`, `ui/src/views/Review.jsx`, `ui/src/stores/useStore.js`

### Iteration A — Proposal generation
`services/link_proposals.py`:
- `generate_link_proposals(note_id: str, top_k: int = 5) -> list[dict]`
  - Uses existing semantic search (`services/search.py`) to find top-k similar notes
  - Filters out already-linked notes and self
  - For each candidate, calls Claude to score relevance and generate a one-line rationale
  - Returns `[{ note_id, note_excerpt, link_type, score, rationale }]`
- Run on every new note after embedding is generated (async background task)

New table `link_proposals`:
```python
class LinkProposal(BaseModel):
    __tablename__ = "link_proposals"
    src_id    = Column(String(36), ForeignKey("notes.id"))
    dst_id    = Column(String(36), ForeignKey("notes.id"))
    score     = Column(Float)
    rationale = Column(Text)
    status    = Column(String(16), default="pending")  # pending|accepted|dismissed
```

### Iteration B — API
`GET /api/v1/notes/<id>/proposals` — returns pending link proposals for a note  
`POST /api/v1/proposals/<id>/accept` — creates Link record, marks proposal accepted  
`POST /api/v1/proposals/<id>/dismiss` — marks proposal dismissed (never re-proposed)  
`GET /api/v1/proposals?status=pending&limit=20` — global proposal queue

### Iteration C — UI: proposals in NoteDetailView
In the backlinks panel (P1-WS4-C), add a "Suggested Links" section below manual backlinks:
```
✦ AI suggests linking to:
  "Meeting notes from Q1 planning — 87% similar" [Accept] [Dismiss]
  "Project kickoff doc for Agent Platform — related" [Accept] [Dismiss]
```
Accept → creates link, moves to confirmed backlinks. Dismiss → hides forever.

### Iteration D — UI: proposals in Review view
Add "Link Proposals" card to Review/Today views:  
"You have 12 unreviewed link suggestions" → expand to show proposal queue.  
Batch accept/dismiss controls.

---

## P3-WS3 — Pattern Detection Agent
**Files:** new `services/patterns.py`, new `api/insights.py`, `ui/src/views/Dashboard.jsx`, `Dashboard.module.css`

### Iteration A — Pattern detection service
`services/patterns.py`:
- `detect_orphan_notes(threshold_days: int = 7) -> list[Note]`  
  Notes with zero links, no project, no area, older than N days
- `detect_project_candidates(min_notes: int = 5) -> list[dict]`  
  Clusters of notes sharing tags/area with no project → suggest creating a project  
  Uses tag co-occurrence and semantic clustering from existing embeddings
- `detect_stale_projects() -> list[Project]`  
  Projects with no new notes in 14 days and incomplete tasks
- `detect_overloaded_inbox(threshold: int = 20) -> bool`  
  Inbox count over threshold → surface routing suggestion
- `generate_insights() -> list[dict]`  
  Runs all detectors, returns prioritized list of insights

### Iteration B — Insights API
`GET /api/v1/insights` — returns current insights list:
```json
[
  { "type": "orphan_notes", "count": 8, "message": "8 notes have no connections", "action": "review" },
  { "type": "project_candidate", "tag": "migration", "note_count": 11, "message": "11 notes tagged #migration have no project", "action": "create_project" },
  { "type": "stale_project", "project_id": "...", "name": "Agent Memory", "last_activity": "14 days ago" }
]
```

### Iteration C — Dashboard insights panel
`Dashboard.jsx`: add "Insights" card above recent notes:  
Each insight shows icon, message, and primary action button.  
"Create project from #migration notes" → opens project creation modal pre-populated.  
"Review 8 orphan notes" → navigates to filtered notes view.  
"Dismiss" per insight (persisted to localStorage for 7 days).

### Iteration D — Insights in weekly review
`Review.jsx` weekly tab: add "System Health" section with all current insights.  
Shows week-over-week change: "Orphan notes: 8 (↑3 from last week)".

---

## P3-WS4 — Automated Capture Pipelines
**Files:** new `api/webhooks.py`, new `services/capture.py`, `ui/src/views/Dashboard.jsx`

### Iteration A — Webhook ingestion endpoint
`POST /api/v1/webhooks/capture` — authenticated endpoint for external capture:
```json
{ "source": "email|slack|browser|mobile", "content": "...", "url": "...", "title": "..." }
```
Validates API key (`X-Engram-Key` header). Runs through existing ingestion pipeline.  
Returns created note with AI classification.

### Iteration B — Email ingestion
`POST /api/v1/webhooks/email` — accepts forwarded emails (via Postmark/SendGrid inbound webhook).  
Parses subject as note title, body as content, strips email threading boilerplate.  
Strips quoted replies (>3 levels) and signatures.

### Iteration C — Browser extension API
`POST /api/v1/webhooks/clip` — web clipper endpoint:  
Body: `{ url, title, selected_text, full_text, author, published_date }`  
Creates a Resource (if URL) or Note (if selected text only).  
Returns created entity + classification.

### Iteration D — Capture source tracking
Add `source` column to Note (already partially exists as `ai_meta.source`):  
Make it a proper column: `source = Column(String(64), nullable=True)`.  
Values: `"manual"`, `"email"`, `"web_clip"`, `"webhook"`, `"import"`, `"daily"`.  
Filter by source in Notes view. Show source badge on note cards (small icon).

---

---

# PHASE 4 — Review, Reflection & Health
> Goal: Close the PKM loop. Make review frictionless. Surface system health. Enable project→area knowledge rollup when projects complete.  
> Prerequisite: Phase 3 intelligence services available.

---

## P4-WS1 — Weekly Review Overhaul
**Files:** `ui/src/views/Review.jsx`, `Review.module.css`, `ui/src/views/Today.jsx`

### Iteration A — Structured review workflow
Replace static layout with a guided review flow — a step-by-step process:
1. **Clear Inbox** — route remaining inbox items (shows count + quick-route controls)
2. **Review Projects** — each active project: last note, open tasks, stale flag
3. **Review Areas** — each area: recent notes, active project count
4. **Orphan Notes** — notes with no connections, surfaced for linking or deletion
5. **Link Proposals** — pending AI link suggestions to accept/dismiss
6. **Insights** — system health signals from P3-WS3
7. **Plan next week** — open tasks due next 7 days, quick add task area

Progress bar at top. Each section collapsible. "Mark complete" per section.  
State persisted in localStorage so review can be paused and resumed.

### Iteration B — Orphan note review
Step 4 UI: list of orphan notes (zero links, no project, no area).  
Per note: quick-assign project/area dropdown, quick-link to another note, or archive.  
"Archive all orphans" bulk action with confirmation.

### Iteration C — Weekly digest summary card
Top of Review: auto-generated digest for the past week:  
"You captured 23 notes, created 4 tasks, completed 2 projects, made 8 connections."  
Stats sourced from DB queries over the week date range.

---

## P4-WS2 — PKM Health Metrics Dashboard
**Files:** new `api/health_metrics.py`, `ui/src/views/Dashboard.jsx`, `Dashboard.module.css`

### Iteration A — Health metrics API
`GET /api/v1/metrics/health`:
```json
{
  "total_notes": 847,
  "orphan_rate": 0.12,           // notes with 0 links / total
  "avg_links_per_note": 3.4,
  "inbox_count": 23,
  "archive_ratio": 0.31,         // archived / total
  "tag_coverage": 0.78,          // notes with >= 1 tag / total
  "active_projects": 8,
  "stale_projects": 2,           // no activity in 14 days
  "weekly_capture_rate": 18,     // notes added last 7 days
  "link_proposals_pending": 47,
}
```

### Iteration B — Dashboard health card
`Dashboard.jsx`: add "Knowledge Health" card with sparkline metrics:  
Orphan rate (lower is better → green/yellow/red indicator).  
Avg links per note (target: 3–8 for regular notes).  
Weekly capture rate trend (last 4 weeks as mini bar chart).  
Inbox count with urgency color (>20 = yellow, >50 = red).

### Iteration C — Health history tracking
Store weekly health snapshots in `weekly_summaries` with `entity_type="system"`.  
Show 12-week trend chart in Review → System Health tab.

---

## P4-WS3 — Project Completion → Area Rollup
**Files:** `api/projects.py`, new `services/rollup.py`, `ui/src/views/ProjectFocus.jsx`, `ui/src/views/AreaFocus.jsx`

### Iteration A — Rollup service
`services/rollup.py`:
- `rollup_project_to_area(project_id: str) -> dict`
  - Summarizes all project notes with Claude
  - Creates a new note in the parent Area with the summary
  - Tags it `#retrospective #project-complete`
  - Archives the project
  - Returns the created summary note

### Iteration B — Archive project flow
When archiving a project (existing `is_archived = True` flag + PATCH endpoint):  
If project has a parent area → trigger rollup (with user confirmation).  
`ProjectFocus.jsx`: "Complete Project" button (not just archive):  
Step 1: confirm "Generate retrospective and roll up to {Area}?"  
Step 2: rollup runs, shows created summary note.  
Step 3: project archived, navigate to area.

### Iteration C — Retrospective note template
Rollup prompt template:
```
You completed the project "{name}".
Here are all {n} notes from this project:
{notes}

Write a concise retrospective covering:
- What was accomplished
- Key decisions made
- Lessons learned
- Outstanding items to carry forward
Format as markdown.
```

---

---

# PHASE 5 — Advanced UX & Graph Intelligence
> Goal: Power-user features. Graph becomes navigable and meaningful. Maps of Content emerge. Templates reduce capture friction. App is fully keyboard-navigable.  
> Prerequisite: Phase 3 link data and Phase 4 health metrics available.

---

## P5-WS1 — Graph View Overhaul
**Files:** `ui/src/views/Graph.jsx`, `Graph.module.css`

### Iteration A — Richer node types and link visualization
Current graph shows notes/projects/areas/people as basic shapes.  
Add: Resource nodes (square with border). Daily note nodes (calendar icon).  
Link lines: different colors per type (related=purple, child_of=blue, depends_on=orange, mentions=grey).  
Link thickness proportional to `weight` (semantic similarity strength).

### Iteration B — Cluster detection and visual grouping
Use D3 force clustering: nodes grouped by project/area with a light hull background.  
Hull color matches project/area color. Label at top of each cluster.  
"Cluster by: Project | Area | Tag | None" toggle in graph controls.

### Iteration C — Heat map mode
"Activity heat map" toggle: node size proportional to note's backlink count.  
Highly-connected notes (MOC candidates) appear as larger nodes.  
Color spectrum: low activity (grey) → high activity (bright accent).

### Iteration D — Graph search and filter
Filter panel: show only nodes of selected types, only nodes in selected projects/areas.  
Search by label: zoom to + highlight matching node.  
"Focus mode": select a node → show only it + direct neighbors (1-hop).

---

## P5-WS2 — Maps of Content (MOC)
**Files:** `models.py`, new `api/moc.py`, new `ui/src/views/MOCView.jsx`, `ui/src/views/NoteDetailView.jsx`, `ui/src/components/layout/AppShell.jsx`

### Iteration A — MOC note type
Add `note_type` column to Note:
```python
class NoteType(PyEnum):
    NOTE    = "NOTE"      # regular note (default)
    MOC     = "MOC"       # Map of Content — index/hub note
    DAILY   = "DAILY"     # daily journal note
    MEETING = "MEETING"   # meeting notes
    DECISION = "DECISION" # decision record

note_type = Column(Enum(NoteType), default=NoteType.NOTE)
```

MOC notes render with a special header and an auto-generated table of contents from their outgoing links.

### Iteration B — AI-generated MOC suggestions
When a cluster of notes (same tag + area) exceeds 8 items with no MOC:  
`POST /api/v1/moc/generate` body `{ note_ids: [...] }`:  
Claude generates a MOC note with: title, overview paragraph, organized sections linking to source notes.  
Creates the MOC note and links it to all source notes as `child_of`.

### Iteration C — MOC view and navigation
New route `/moc` → `MOCView.jsx`: lists all MOC notes with their linked-note counts.  
In NoteDetailView: badge if this note is a MOC. Show linked note count prominently.  
In Graph: MOC nodes appear larger, with a distinct icon.  
AppShell: "MOCs" section in sidebar listing top MOC notes.

---

## P5-WS3 — Template System
**Files:** new `models.py` additions, new `api/templates.py`, new `migrations/008_*.py`, `ui/src/components/notes/NoteEditor.jsx`, `ui/src/views/Today.jsx`

### Iteration A — Template model
```python
class Template(BaseModel):
    __tablename__ = "templates"
    name         = Column(String(255), nullable=False)
    description  = Column(String(500), nullable=True)
    content      = Column(Text, nullable=False)   # markdown with {{variable}} placeholders
    note_type    = Column(Enum(NoteType), default=NoteType.NOTE)
    default_bucket = Column(Enum(BucketType), default=BucketType.INBOX)
    is_builtin   = Column(Boolean, default=False)
```

Seed built-in templates:
- **Meeting Notes**: `# Meeting — {{date}}\n## Attendees\n## Agenda\n## Notes\n## Action Items\n- [ ] `
- **Decision Record**: `# Decision: {{title}}\n## Context\n## Options\n## Decision\n## Consequences`
- **Project Kickoff**: `# {{project}} Kickoff\n## Goal\n## Scope\n## Timeline\n## Risks`
- **Weekly Review**: (pre-filled daily review format)
- **Book Notes**: `# {{title}} by {{author}}\n## Key Ideas\n## Quotes\n## My Notes`

### Iteration B — API
`GET /api/v1/templates` — list all templates  
`POST /api/v1/templates` — create custom template  
`PATCH /api/v1/templates/<id>`, `DELETE /api/v1/templates/<id>`  
`POST /api/v1/templates/<id>/instantiate` — replace `{{variables}}` with provided values, return filled content

### Iteration C — UI: template picker in NoteEditor and QuickCapture
NoteEditor: "Use template" button → dropdown of templates → selecting one fills textarea.  
QuickCapture: `/template` slash command: type `/meeting` → loads Meeting Notes template.  
Variable substitution modal: if template has `{{date}}`, `{{title}}` etc., show a small form before filling.

---

## P5-WS4 — Full Keyboard Navigation & Accessibility
**Files:** `ui/src/App.jsx`, `ui/src/views/*.jsx`, `ui/src/components/**/*.jsx`

### Iteration A — Extended keyboard shortcuts
Expand global shortcuts (from P1-WS6-C):
```
n       → new note (QuickCapture)
/       → search (CommandPalette)
i       → inbox
t       → tasks
g       → graph
r       → review
p       → projects
a       → areas
d       → today (daily note)
j / k   → next / prev item in any list
Enter   → open selected
e       → edit (in detail views)
Esc     → back / close
⌘s      → save (in editor)
⌘↵      → save and new
?       → keyboard help
```

### Iteration B — Focus management
All modals: trap focus, restore on close, announce with aria-live.  
All icon-only buttons: `aria-label` on every `<button>` without visible text.  
NoteDetailView: focus textarea on entering edit mode.  
CommandPalette: auto-focus search input on open.

### Iteration C — Screen reader support
Add `role`, `aria-label`, `aria-expanded`, `aria-current="page"` throughout.  
Graph: keyboard-navigable node selection (arrow keys move focus between nodes).  
Task kanban: keyboard column movement (left/right arrow between columns).

### Iteration D — Mobile responsiveness
Audit all views on 375px width. Sidebar: slide-in drawer on mobile (touch swipe).  
NoteCard: full width. NoteEditor: single column. Kanban: horizontal scroll.  
QuickCapture: bottom sheet on mobile (full width, slides up from bottom).

---

---

# Full File Ownership Map (All Phases)

| File | Phase | Workstream |
|------|-------|-----------|
| `models.py` | P1, P2, P3, P5 | P1-WS1, P2-WS1, P2-WS2, P2-WS3, P3-WS2, P3-WS4, P5-WS2, P5-WS3 |
| `api/projects.py` | P1, P2, P4 | P1-WS1, P2-WS4, P4-WS3 |
| `api/tasks.py` | P1 | P1-WS1 |
| `api/areas.py` | P1 | P1-WS1 |
| `api/notes.py` | P1, P2 | P1-WS1, P2-WS1 |
| `api/daily.py` *(new)* | P1 | P1-WS1 |
| `api/resources.py` *(new)* | P2 | P2-WS2 |
| `api/proposals.py` *(new)* | P3 | P3-WS2 |
| `api/insights.py` *(new)* | P3 | P3-WS3 |
| `api/webhooks.py` *(new)* | P3 | P3-WS4 |
| `api/health_metrics.py` *(new)* | P4 | P4-WS2 |
| `api/moc.py` *(new)* | P5 | P5-WS2 |
| `api/templates.py` *(new)* | P5 | P5-WS3 |
| `services/extractor.py` | P1 | P1-WS1 |
| `services/summarizer.py` *(new)* | P3 | P3-WS1 |
| `services/link_proposals.py` *(new)* | P3 | P3-WS2 |
| `services/patterns.py` *(new)* | P3 | P3-WS3 |
| `services/capture.py` *(new)* | P3 | P3-WS4 |
| `services/rollup.py` *(new)* | P4 | P4-WS3 |
| `ui/src/stores/useStore.js` | P1, P2, P3 | P1-WS3, P2-WS1, P3-WS2 |
| `ui/src/components/search/CommandPalette.jsx` | P1, P2 | P1-WS3, P2-WS3 |
| `ui/src/components/layout/AppShell.jsx` | P1, P2, P5 | P1-WS5, P2-WS2, P5-WS2 |
| `ui/src/components/notes/NoteCard.jsx` | P1 | P1-WS2 |
| `ui/src/components/notes/NoteEditor.jsx` | P1, P2, P5 | P1-WS4, P2-WS1, P5-WS3 |
| `ui/src/components/notes/QuickCapture.jsx` *(new)* | P1 | P1-WS6 |
| `ui/src/views/NoteDetailView.jsx` | P1, P3, P5 | P1-WS4, P3-WS2, P5-WS2 |
| `ui/src/views/Inbox.jsx` | P1 | P1-WS4 |
| `ui/src/views/Today.jsx` *(new)* | P1, P4, P5 | P1-WS4, P4-WS1, P5-WS3 |
| `ui/src/views/Tasks.jsx` | P1 | P1-WS3 |
| `ui/src/views/Areas.jsx` | P1, P2 | P1-WS3, P2-WS4 |
| `ui/src/views/AreaFocus.jsx` | P1, P2, P4 | P1-WS5, P2-WS4, P4-WS3 |
| `ui/src/views/Projects.jsx` | P2 | P2-WS4 |
| `ui/src/views/ProjectFocus.jsx` | P1, P2, P4 | P1-WS5, P2-WS4, P4-WS3 |
| `ui/src/views/People.jsx` | P1, P2 | P1-WS3, P2-WS3 |
| `ui/src/views/PersonDetail.jsx` *(new)* | P2 | P2-WS3 |
| `ui/src/views/Resources.jsx` *(new)* | P2 | P2-WS2 |
| `ui/src/views/ResourceDetail.jsx` *(new)* | P2 | P2-WS2 |
| `ui/src/views/Review.jsx` | P3, P4 | P3-WS1, P4-WS1 |
| `ui/src/views/Dashboard.jsx` | P3, P4 | P3-WS3, P4-WS2 |
| `ui/src/views/Graph.jsx` | P1, P5 | P1-WS5, P5-WS1 |
| `ui/src/views/Notes.jsx` | P1 | P1-WS6 |
| `ui/src/views/MOCView.jsx` *(new)* | P5 | P5-WS2 |
| `ui/src/App.jsx` | P1, P5 | P1-WS6, P5-WS4 |
| `ui/src/index.css` | P1 | P1-WS2 |

---

# Dependency Graph (Phase-Level)

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4
                    │                    │
                    └────────────────────┴──► Phase 5
```

Within each phase, all workstreams run in parallel.  
A later phase's WS may start once the specific earlier WS it depends on is merged — not the full phase.  
e.g., P3-WS1 (summarization) only needs P1-WS1 (schema) + existing WeeklySummary model, not all of Phase 2.
