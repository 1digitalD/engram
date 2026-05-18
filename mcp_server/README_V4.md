# Engram v4 MCP

The v4 MCP server is read-only.

Exposed tools:

- `search_entities(query, entity_type?, limit?)`
- `get_entity(entity_id, include_relationships?)`
- `list_recent(entity_type?, limit?)`

Intentionally not exposed:

- capture
- create task/entity
- update entity
- link entities
- delete entity

Smoke test:

```bash
ENGRAM_API_BASE=http://localhost:5001/api/v4 python mcp_server/server.py
```

For HTTP-capable MCP clients:

```bash
TRANSPORT=http MCP_PORT=8765 ENGRAM_API_BASE=http://localhost:5001/api/v4 python mcp_server/server.py
```
