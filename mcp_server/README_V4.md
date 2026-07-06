# Engram v4 MCP

The v4 MCP server is a thin REST proxy — it translates MCP tool calls into `/api/v4`
requests and returns formatted text. It is write-enabled and has no separate permissions or state.

## Exposed tools

**Read:**
- `search_entities(query?, entity_type?, mode?, status?, lifecycle?, tag?, limit?)` — search entities with hybrid/keyword/semantic or tag-only retrieval
- `get_entity(entity_id, include_relationships?)` — canonical entity or detail view
- `list_recent(entity_type?, limit?)` — recently updated active entities
- `get_today()` — follow-ups, blocked/waiting tasks, active projects, recent notes, pending suggestions
- `list_suggestions(status?)` — AI suggestions awaiting review (default: pending)
- `get_agent_activity(limit?)` — recent agent automation actions, suggestions, and failures

**Write:**
- `capture(content, source?)` — save raw text as a note, triggers server-side extraction
- `create_entity(type, title, content?, tags?, status?, due_at?, follow_up_at?)` — create pre-classified entity
- `update_entity(entity_id, title?, content?, status?, lifecycle?, due_at?, follow_up_at?, tags?)` — update entity fields
- `link_entities(source_id, target_id, relationship_type?, evidence?)` — create EntityLink
- `accept_suggestion(suggestion_id)` — accept AI suggestion, creating the suggested entity
- `dismiss_suggestion(suggestion_id)` — dismiss AI suggestion without acting
- `reconcile_suggestions(limit?)` — expire pending suggestions that no longer apply
- `submit_candidates(entity_id, summary?, tags?, entities?, links?)` — submit pre-extracted candidates for any entity, bypassing LLM extraction
- `append_activity_update(entity_id, content, skip_extraction?)` — append an activity update note to a project, task, or area (exact duplicates within 24h skipped; near-duplicates flagged; set `skip_extraction=true` to skip lightweight extraction)

## Transport

**stdio** (default for Claude CLI / Cursor / Codex):
```bash
ENGRAM_API_BASE=http://localhost:5001/api/v4 python mcp_server/server.py
```

**HTTP** (for web-capable clients):
```bash
TRANSPORT=http MCP_PORT=8765 ENGRAM_API_BASE=http://localhost:5001/api/v4 python mcp_server/server.py
```

When exposing MCP through Tailscale Serve, set `MCP_ALLOWED_HOSTS` to your
machine's Tailscale DNS name (comma-separated if needed). FastMCP validates the
`Host` header and returns `421 Misdirected Request` for unknown hosts — this is
not a TLS certificate problem.

```bash
MCP_ALLOWED_HOSTS=danishs-mac-mini.tail003386.ts.net \
TRANSPORT=http MCP_PORT=8765 \
ENGRAM_API_BASE=http://127.0.0.1:5001/api/v4 \
python mcp_server/server.py
```

## Smoke test

```bash
cd /Volumes/lex1t/dev/shared/repos/engram
ENGRAM_API_BASE=http://localhost:5001/api/v4 ./venv/bin/python mcp_server/server.py
```

The server starts in stdio mode by default. Press Ctrl-C to stop.
