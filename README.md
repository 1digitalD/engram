# Engram

Personal knowledge management with PARA methodology and AI-powered recall.

> An engram is a physical trace in the brain that stores a memory.

## Quick Start

```bash
git clone https://github.com/1digitalD/engram
cd engram

# Backend
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your OPENAI_API_KEY to .env if you want AI extraction/classification
export FLASK_APP=app.py
flask init-db
PORT=5001 flask run

# Frontend (in a separate terminal)
cd ui
npm install
npm run dev      # dev server at http://localhost:5173 (proxies API to :5001)
npm run build    # production build → ../static/
```

Open http://localhost:5001 in your browser.

## MCP

Engram ships with a local MCP server at `mcp_server/server.py`.

### STDIO transport, best for Claude Desktop and local assistants

```bash
cd /path/to/engram
source venv/bin/activate
export ENGRAM_API_BASE=http://localhost:5001/api/v1
python mcp_server/server.py
```

### Streamable HTTP transport, best for HTTP-capable MCP clients

```bash
cd /path/to/engram
source venv/bin/activate
export ENGRAM_API_BASE=http://localhost:5001/api/v1
export TRANSPORT=http
export MCP_PORT=8765
python mcp_server/server.py
```

Or serve the exported ASGI app directly:

```bash
cd /path/to/engram
source venv/bin/activate
export ENGRAM_API_BASE=http://localhost:5001/api/v1
uvicorn mcp_server.server:mcp_app --host 127.0.0.1 --port 8765
```

### Smoke checks

```bash
curl http://localhost:5001/health
curl http://localhost:5001/api/v1/notes
curl -i -H 'Accept: text/event-stream' http://localhost:8765/mcp
```

The MCP server exposes these tools: `capture`, `search`, `get_note`, `list_recent`, `update_note`, `link_notes`, `review`.

## Architecture

```
engram/
├── app.py            # Flask backend (serves API + static/ at /)
├── api/              # REST API (notes, projects, tasks, people, areas, tags)
├── models.py         # SQLAlchemy models + FTS5 search
├── services/
│   ├── classifier.py # OpenAI GPT-4o PARA classification
│   └── search.py     # Full-text search
├── static/           # Compiled React UI (built from ui/)
│   └── index.html    # SPA entry point
└── ui/               # React + Vite source
    ├── src/
    │   ├── views/    # Dashboard, Notes, Projects, Tasks, People, Areas, Review, Graph
    │   ├── components/ # layout, ui, search, notes components
    │   ├── stores/   # Zustand state
    │   └── api/      # Engram API client
    ├── vite.config.js
    └── package.json
```

## Features

- **Auto-classification** — notes are AI-classified into PARA buckets with project/area linking
- **Full-text search** — SQLite FTS5 across all notes
- **Command palette** — `⌘K` for fuzzy search + quick actions
- **Kanban tasks** — drag between Inbox/Open/In Progress/Done
- **Graph view** — D3 force-directed network of all entities
- **Weekly review** — inbox digest + project/task summary
- **REST API** — full CRUD at `/api/v1/*`

## Tech Stack

- Flask + SQLAlchemy + SQLite (FTS5)
- React 18 + Vite (frontend SPA)
- OpenAI GPT-4o (classification)
- Zustand (state) + Lucide icons

## API

```bash
# Health
curl http://localhost:5001/health

# Create note (auto-classifies)
curl -X POST http://localhost:5001/api/v1/notes \
  -H "Content-Type: application/json" \
  -d '{"raw_text": "Your note here"}'

# List notes
curl http://localhost:5001/api/v1/notes

# Search
curl "http://localhost:5001/api/v1/notes/search?q=keyword"
```

## Status

MVP complete. See [SPEC.md](SPEC.md) for full specification.
