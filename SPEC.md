# Engram v2 — Specification

> An AI-native personal knowledge management system. An engram is a physical memory trace in the brain — knowledge that persists and can be recalled at the right moment.

---

## 1. Vision

**Goal:** A self-hosted second brain that captures anything (text, image, PDF, audio, URLs), classifies it intelligently using the PARA method, makes it findable through hybrid semantic + keyword search, and exposes everything to AI agents via a native MCP server.

**Target user:** Single user (Dan), self-hosted on Mac Mini.

**Core principle:** AI handles classification, entity extraction, and linking automatically. The user focuses on capture and review; the system handles organization.

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         CLIENTS                              │
│  Web UI (React)    Hermes (Discord)    Claude / any MCP agent│
└──────────┬──────────────────┬────────────────┬──────────────┘
           │ HTTP             │ MCP (STDIO)    │ MCP (STDIO)
           ▼                  ▼                ▼
┌──────────────────┐   ┌─────────────────────────────┐
│  Flask REST API  │   │     fastmcp MCP Server       │
│  flask-openapi3  │   │  capture · search · review   │
│  /api/v1/batch   │   │  get_note · link · list      │
│  /api/v1/events  │   └──────────────┬──────────────┘
│    (SSE stream)  │                  │ HTTP
└────────┬─────────┘──────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│                 Ingestion Pipeline                    │
│                                                      │
│  Multi-modal intake                                  │
│  ├── Text: direct                                    │
│  ├── Image: GPT-4o vision (base64)                   │
│  ├── PDF: pymupdf4llm → Markdown                     │
│  ├── Audio: OpenAI whisper-1                         │
│  └── URL: trafilatura                                │
│                                                      │
│  GPT-4o Structured Extraction (single call)          │
│  ├── PARA bucket + confidence                        │
│  ├── Tasks (title, due, priority)                    │
│  ├── People (name, email)                            │
│  ├── Project/area match                              │
│  └── Tags (2-6)                                      │
│                                                      │
│  Entity Resolution (cascade)                         │
│  ├── 1. Exact normalized match                       │
│  ├── 2. rapidfuzz token_set_ratio ≥ 88               │
│  └── 3. Embedding cosine ≥ 0.85                      │
│                                                      │
│  Auto-create at confidence ≥ 85%                     │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────────────┐
         │         engram.db (SQLite)      │
         │  notes · projects · areas       │
         │  tasks · people · tags          │
         │  note_chunks (embedding chunks) │
         │  links (graph adjacency)        │
         │  notes_fts (FTS5 virtual)       │
         │  vec_chunks (sqlite-vec)        │
         └─────────────────────────────────┘
                       │
           ┌───────────┼───────────┐
           ▼           ▼           ▼
    ┌─────────┐  ┌──────────┐  ┌───────┐
    │  FTS5   │  │ sqlite-  │  │ Links │
    │  BM25   │  │   vec    │  │ graph │
    │ search  │  │  kNN     │  │ RDF   │
    └────┬────┘  └────┬─────┘  └───────┘
         └────────────┘
              RRF fusion (k=60)
              Hybrid search
```

---

## 3. Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, Flask 3.x, Flask-SQLAlchemy 3.x |
| Database | SQLite with FTS5 (full-text) + sqlite-vec (vector) |
| AI | OpenAI GPT-4o (extraction, vision), text-embedding-3-small, whisper-1 |
| Entity extraction | Pydantic + OpenAI Structured Outputs (strict mode) |
| Entity resolution | exact match → rapidfuzz → embedding cosine |
| PDF extraction | pymupdf4llm → Markdown |
| Web extraction | trafilatura 2.x |
| MCP server | fastmcp (STDIO for local, Streamable HTTP for remote) |
| Frontend | React 19, Vite 8, Zustand, React Router 7, D3 (graph view) |

---

## 4. Data Models

### Note (core entity)
```
id: UUID
raw_text: TEXT
bucket: ENUM (INBOX|PROJECTS|AREAS|RESOURCES|ARCHIVES)
is_archived: BOOLEAN
ai_meta: JSON  {confidence, reasoning, summary, source, extracted_tasks, extracted_people, ...}
project_id: FK → projects (nullable)
area_id: FK → areas (nullable)
person_id: FK → people (nullable)
tags: M2M → tags
created_at, modified_at: DATETIME
```

### Project / Area / Tag / Person / Task / WeeklySummary
(unchanged from v1 schema)

### NoteChunk (new — embedding storage)
```
id: UUID (= note_id + "_" + chunk_index)
note_id: FK → notes
chunk_index: INT
chunk_text: TEXT
embedding_model: TEXT  (default: text-embedding-3-small)
created_at: DATETIME
```

### Link (new — knowledge graph)
```
id: UUID
src_id: FK → notes
dst_id: FK → notes
link_type: TEXT  (related|child_of|depends_on|see_also|mentions)
weight: FLOAT  (1.0 = manual, 0-1 = embedding similarity)
source: TEXT  (manual|embedding|llm|wikilink)
created_at: DATETIME
```

### Virtual tables
```
notes_fts: FTS5 virtual table (content='notes', content_rowid='rowid')
vec_chunks: vec0 virtual table (chunk_id TEXT, embedding FLOAT[1536])
```

---

## 5. API Routes

Base URL: `http://localhost:5001/api/v1`

### Core Ingestion
| Method | Endpoint | Description |
|---|---|---|
| POST | `/ingest` | Smart multi-modal ingestion (text, image, PDF, audio, URL) |
| POST | `/batch` | Execute up to 50 operations in one request |

### Notes
| Method | Endpoint | Description |
|---|---|---|
| GET | `/notes` | List notes (bucket, project_id, area_id, tag_id, archived, limit, offset) |
| POST | `/notes` | Create note with AI classification |
| GET | `/notes/<id>` | Get note |
| PATCH | `/notes/<id>` | Update note (text, bucket, tags, project, archive) |
| DELETE | `/notes/<id>` | Delete note |
| GET | `/notes/search?q=&mode=hybrid` | Hybrid search (fts\|semantic\|hybrid) |
| GET | `/notes/<id>/links` | Get outgoing + incoming graph links |
| GET | `/notes/<id>/related` | Get semantically related notes |

### Knowledge Graph
| Method | Endpoint | Description |
|---|---|---|
| POST | `/links` | Create manual link |
| DELETE | `/links/<id>` | Remove link |

### Projects / Areas / Tags / People / Tasks
Standard CRUD for each, all using PATCH for updates.

### Summaries / Health
Unchanged from v1.

---

## 6. MCP Server Tools

Located at `mcp/server.py`. Run with `python mcp/server.py` (STDIO transport).

| Tool | Description |
|---|---|
| `capture(content, source?, media_url?, media_type?, media_base64?, media_mime?)` | Ingest anything into Engram |
| `search(query, mode?, bucket?, project_id?, limit?)` | Hybrid semantic + keyword search |
| `get_note(note_id, include_links?)` | Fetch note with full metadata and backlinks |
| `list_recent(scope?, limit?, project_id?)` | Inbox / recent notes / pending tasks |
| `update_note(note_id, ...)` | Edit, re-route, archive a note |
| `link_notes(src_id, dst_id, link_type?)` | Create knowledge graph link |
| `review(scope?)` | Daily/weekly digest of items needing attention |

### Claude Desktop / Code integration
Add to `~/.claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "engram": {
      "command": "python",
      "args": ["/path/to/engram/mcp/server.py"],
      "env": { "ENGRAM_API_BASE": "http://localhost:5001/api/v1" }
    }
  }
}
```

---

## 7. Ingestion Pipeline Detail

### `/api/v1/ingest` body
```json
{
  "content": "text content (required if no media)",
  "source": "discord|web|api|hermes",
  "media_url": "https://...",
  "media_type": "image|pdf|audio|url",
  "media_base64": "base64 string",
  "media_mime": "image/jpeg"
}
```

### Pipeline steps
1. **Media extraction** — image→GPT-4o vision, PDF→pymupdf4llm, audio→Whisper, URL→trafilatura
2. **AI extraction** — GPT-4o Structured Outputs (single call):
   - PARA bucket + confidence (self-reported 0-1)
   - Tasks (title, due_date, priority, project_hint)
   - People (name, email, context)
   - Suggested project + area names
   - Tags (2-6, lowercase)
3. **Entity resolution** — exact → rapidfuzz ≥ 88 → embedding cosine ≥ 0.85
4. **Auto-create** — new entities created if confidence ≥ 0.85
5. **Note creation** — linked to resolved project/area/person/tags
6. **Background** — embedding generation + auto-link discovery (threaded)

### Confidence gating
- ≥ 0.85: auto-create entities, route to correct bucket
- < 0.85: note placed in INBOX, extracted entities stored in ai_meta only

---

## 8. Search

### Hybrid RRF
```
fts_results = FTS5 BM25 top 60
sem_results = sqlite-vec cosine kNN top 60
rrf_score(d) = Σ 1/(60 + rank_i)  across systems
return top 20 by rrf_score
```

### Embedding strategy
- Model: `text-embedding-3-small` @ 1536 dims
- Chunking: Markdown heading splits → 400-token sliding window, 64-token overlap
- Chunk prefix: breadcrumb (e.g. "Project: Q3 > Meeting notes 2026-04-12: ...")
- Stored in: `note_chunks` (metadata) + `vec_chunks` (sqlite-vec virtual table)

---

## 9. Setup

```bash
git clone https://github.com/1digitalD/engram
cd engram
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # add OPENAI_API_KEY
flask init-db           # creates tables, FTS5, sqlite-vec
flask run --port 5001   # start backend
flask embed-backfill    # generate embeddings for existing notes (optional)

# Frontend
cd ui
npm install
npm run dev             # dev server at :5173 with proxy to :5001
npm run build           # compile to ../static/

# MCP server (separate terminal)
cd mcp
pip install -r requirements.txt
python server.py
```

---

## 10. Environment Variables

```
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=change-me-in-production
DATABASE_URL=sqlite:///engram.db
OPENAI_API_KEY=sk-...
PORT=5001
LOG_LEVEL=INFO

# MCP server
ENGRAM_API_BASE=http://localhost:5001/api/v1
TRANSPORT=stdio   # or: http
MCP_PORT=8765     # only used when TRANSPORT=http
```

---

## 11. File Structure

```
engram/
├── app.py                  # Flask app factory, CLI commands
├── config.py               # Config profiles
├── extensions.py           # db + sqlite-vec loader
├── models.py               # All SQLAlchemy models + FTS5/vec init
├── requirements.txt
├── .env.example
├── SPEC.md
├── README.md
│
├── api/
│   ├── __init__.py         # Blueprint, imports all sub-modules
│   ├── notes.py            # Notes CRUD + search
│   ├── projects.py         # Projects CRUD
│   ├── areas.py            # Areas CRUD
│   ├── tags.py             # Tags CRUD
│   ├── people.py           # People CRUD
│   ├── tasks.py            # Tasks CRUD
│   ├── summaries.py        # Weekly summaries
│   ├── ingest.py           # Smart ingestion endpoint
│   ├── links.py            # Knowledge graph endpoints
│   └── batch.py            # Batch operations
│
├── services/
│   ├── classifier.py       # Legacy PARA classifier (used by /notes)
│   ├── extractor.py        # GPT-4o Structured Outputs extraction
│   ├── ingestion.py        # Multi-modal pipeline + entity resolution
│   ├── embeddings.py       # sqlite-vec storage, hybrid search helpers
│   ├── search.py           # Hybrid FTS5 + vec search with RRF
│   └── links.py            # Graph link helpers
│
├── mcp/
│   ├── server.py           # fastmcp MCP server (7 tools)
│   └── requirements.txt    # fastmcp, httpx
│
├── ui/
│   ├── src/
│   │   ├── api/engram.js   # API client (all endpoints, relative URLs)
│   │   ├── stores/         # Zustand state
│   │   ├── views/          # Page components
│   │   └── components/     # Shared UI components
│   ├── package.json
│   └── vite.config.js      # Proxies /api → :5001
│
├── static/                 # Compiled React bundle (served by Flask)
├── instance/engram.db      # SQLite database
├── tests/                  # pytest suite
└── venv/                   # Python virtual environment
```

---

## 12. Roadmap

### Done (v2)
- [x] Smart ingestion pipeline (`/ingest`) with GPT-4o Structured Outputs
- [x] Multi-modal: image (GPT-4o vision), PDF (pymupdf4llm), audio (whisper-1), URL (trafilatura)
- [x] Entity resolution: exact → rapidfuzz → embedding cascade
- [x] Confidence-gated auto-create (≥ 85%)
- [x] Real AI confidence scores (self-reported, not hardcoded)
- [x] Tag creation + linking fixed
- [x] Knowledge graph (links table, backlinks, related notes)
- [x] Embeddings (text-embedding-3-small, 1536 dims, chunked)
- [x] sqlite-vec integration for vector search
- [x] Hybrid FTS5 + vector search with RRF (k=60)
- [x] MCP server (fastmcp, STDIO, 7 high-leverage tools)
- [x] Batch API (`/batch`, up to 50 ops)
- [x] GET /tasks/<id> and GET /tags/<id> added
- [x] Frontend API client: relative URLs, PATCH (not PUT), ingest + links + batch APIs
- [x] Flask runs on port 5001 (matches Vite proxy)

### Next
- [ ] Daily/weekly review automation (agent-triggered digest)
- [ ] Proactive surfacing (embedding of current context → surface old notes)
- [ ] Stale project detection + auto-archive suggestions
- [ ] Web clipper (browser extension or bookmarklet)
- [ ] Daily notes page in UI
- [ ] Knowledge graph view improvements (clusters, PageRank)
- [ ] SSE event stream (`/events/stream`) for reactive agents
- [ ] Auto-summarization with progressive depth
- [ ] Spaced repetition for ideas
- [ ] OpenAPI spec auto-generation (flask-openapi3)
