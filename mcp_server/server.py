#!/usr/bin/env python3
"""Engram v4 read-only MCP server."""

import os
import sys
from typing import Optional

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from fastmcp import FastMCP
except ImportError:
    print("fastmcp not installed. Run: pip install fastmcp", file=sys.stderr)
    sys.exit(1)

from mcp_server.v4_formatters import format_entity, format_recent, format_search_results


ENGRAM_BASE = os.getenv("ENGRAM_API_BASE", "http://localhost:5001/api/v4")
ENGRAM_TIMEOUT = float(os.getenv("ENGRAM_API_TIMEOUT", "60"))

mcp = FastMCP(
    name="engram",
    version="4.0.0",
    instructions=(
        "Engram v4 is a read-only personal workspace surface for MCP clients. "
        "Use search_entities, get_entity, and list_recent to retrieve canonical v4 entities. "
        "This MCP server intentionally exposes no capture, create, update, link, merge, or delete tools."
    ),
)


def _api(method: str, path: str, **kwargs) -> dict:
    url = f"{ENGRAM_BASE}{path}"
    try:
        with httpx.Client(timeout=ENGRAM_TIMEOUT) as client:
            response = getattr(client, method.lower())(url, **kwargs)
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError as exc:
        raise RuntimeError(f"Engram API is unreachable at {ENGRAM_BASE}") from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"Engram API timed out after {ENGRAM_TIMEOUT:.0f}s calling {path}") from exc
    except httpx.HTTPStatusError as exc:
        body = exc.response.text.strip()
        detail = f": {body[:300]}" if body else ""
        raise RuntimeError(f"Engram API {exc.response.status_code} for {path}{detail}") from exc


mcp_app = mcp.http_app(path="/mcp", transport="streamable-http")


@mcp.tool(description="Search v4 entities using Engram hybrid search. Read-only.")
def search_entities(query: str, entity_type: Optional[str] = None, limit: int = 10) -> str:
    limit = max(1, min(limit, 50))
    params = {"q": query, "mode": "hybrid", "limit": limit}
    if entity_type:
        params["type"] = entity_type
    payload = _api("GET", "/search", params=params)
    return format_search_results(payload, query)


@mcp.tool(description="Get one canonical v4 entity, optionally with relationship sections. Read-only.")
def get_entity(entity_id: str, include_relationships: bool = True) -> str:
    path = f"/entities/{entity_id}/detail" if include_relationships else f"/entities/{entity_id}"
    payload = _api("GET", path)
    return format_entity(payload, include_relationships=include_relationships)


@mcp.tool(description="List recent active v4 entities, optionally filtered by entity type. Read-only.")
def list_recent(entity_type: Optional[str] = None, limit: int = 10) -> str:
    limit = max(1, min(limit, 50))
    params = {"limit": limit}
    if entity_type:
        params["type"] = entity_type
    payload = _api("GET", "/recent", params=params)
    return format_recent(payload, entity_type=entity_type)


if __name__ == "__main__":
    transport = os.getenv("TRANSPORT", "stdio")
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=int(os.getenv("MCP_PORT", 8765)))
