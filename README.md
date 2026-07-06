# Engram

Engram is a self-hosted personal workspace for capturing notes, recalling context, and running projects and tasks with AI assistance.

The active implementation is **Engram v4**. v4 is a fresh clean cutover: there is no backward compatibility requirement, no data migration requirement, and existing local app data can be deleted before running v4.

## Quick Start

```bash
git clone https://github.com/1digitalD/engram
cd engram

python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Start Postgres + pgvector.
docker compose up -d

# Optional: start isolated test DB.
docker compose -f docker-compose.test.yml up -d

# Apply the fresh v4 schema. This deletes existing local Engram app data.
flask --app app.py init-db

# Run backend and UI.
PORT=5001 flask --app app.py run
cd ui && npm install && npm run dev
```

Open the UI at `http://localhost:5173` during development, or `http://localhost:5001` after `cd ui && npm run build`.

## v4 Runtime Boundary

The only target runtime API is `/api/v4`.

Obsolete APIs are not v4 targets:

- `/api/v1`
- `/api/v2`

Do not add compatibility adapters for old response shapes. Do not store relationship IDs in `properties`; all relationships must use `EntityLink` records.

If the app returns database errors after upgrading to v4, reset the local database with `flask --app app.py init-db`. v4 is a clean cutover; old v1/v2/v3 table shapes are not migrated or preserved.

## Core v4 Concepts

- Notes remain source artifacts.
- Supported entity types are `note`, `task`, `project`, `area`, `resource`, and `person`.
- Relationships are first-class records with types such as `parent`, `related`, `derived_from`, `mentions`, `assigned_to`, `references`, `blocks`, and `activity_update`.
- AI may safely auto-apply metadata and high-confidence links.
- Risky changes such as entity creation, status changes, deletion, merge, and relationship deletion must be suggestions for review.

## API Examples

```bash
curl http://localhost:5001/api/v4/health

curl -X POST http://localhost:5001/api/v4/capture \
  -H "Content-Type: application/json" \
  -d '{"content": "Ask Henry about rollout", "source": "quick_capture", "mode": "auto"}'

curl http://localhost:5001/api/v4/entities?type=task
curl "http://localhost:5001/api/v4/search?q=rollout&mode=hybrid"
curl http://localhost:5001/api/v4/today
```

## MCP

Engram ships with a v4 write-enabled MCP server at `mcp_server/server.py`. The MCP is a thin proxy over `/api/v4`; it does not hold separate state or permissions.

```bash
cd /path/to/engram
source venv/bin/activate
ENGRAM_API_BASE=http://localhost:5001/api/v4 python mcp_server/server.py
```

Available MCP tools:

- `search_entities`
- `get_entity`
- `list_recent`
- `get_today`
- `list_suggestions`
- `capture`
- `create_entity`
- `update_entity`
- `link_entities`
- `accept_suggestion`
- `dismiss_suggestion`
- `submit_candidates`
- `append_activity_update`

Use `mcp_server/README_V4.md` as the contract for MCP inputs, outputs, and transport modes.

For HTTP transport (local or Tailscale), set `TRANSPORT=http` and `MCP_PORT=8765`.
When proxying through Tailscale Serve, also set `MCP_ALLOWED_HOSTS` to your machine's
Tailscale DNS name — otherwise FastMCP returns `421 Misdirected Request` for the
Tailscale `Host` header (this is not a TLS certificate issue).

## Deployment

For local launchd + Tailscale deployment, use `docs/DEPLOY.md`, `scripts/engram-deploy.sh`,
`com.engram.api.plist`, and `com.engram.mcp.plist`. The API binds to `127.0.0.1:5001`;
MCP HTTP binds to `127.0.0.1:8765` at path `/mcp`.

## Validation

```bash
PYTHONPATH=. ./venv/bin/pytest -q
cd ui && npm test
cd ui && npm run build
```

Schema reset validation is destructive: `flask --app app.py init-db`.

## Active Documentation

- `docs/V4_PRINCIPLES.md`
- `docs/V4_IMPLEMENTATION_PLAN.md`
- `docs/SCHEMA.sql`
- `docs/DEPLOY.md`
- `mcp_server/README_V4.md`
- `EXECUTION-TRACKER.md`

`prd.json` remains in the repo as archived reference material only and is not an active v4 source of truth.
