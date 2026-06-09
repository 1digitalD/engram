#!/usr/bin/env python3
"""Engram v4 MCP server — read and write access to the personal workspace.

V4 MCP exposes both read and write tools. All write tools call through to the
Engram /api/v4 REST API. The MCP is not a separate authority — it is a thin
proxy that translates MCP tool calls into API calls.

Read tools:  search_entities, get_entity, list_recent, get_today, list_suggestions, get_agent_activity
Write tools: capture, create_entity, update_entity, link_entities,
             accept_suggestion, dismiss_suggestion, reconcile_suggestions, submit_candidates

All tools use the same API base (ENGRAM_API_BASE). The MCP server itself
holds no separate state or permissions.
"""

import os
import sys
from typing import List, Optional

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from fastmcp import FastMCP
except ImportError:
    print("fastmcp not installed. Run: pip install fastmcp", file=sys.stderr)
    sys.exit(1)

from mcp_server.v4_formatters import (
    format_agent_activity,
    format_activity_update,
    format_capture_result,
    format_entity,
    format_entity_write,
    format_link,
    format_recent,
    format_search_results,
    format_suggestion_reconcile,
    format_suggestion_action,
    format_suggestions,
    format_today,
)


ENGRAM_BASE = os.getenv("ENGRAM_API_BASE", "http://localhost:5001/api/v4")
ENGRAM_TIMEOUT = float(os.getenv("ENGRAM_API_TIMEOUT", "60"))

mcp = FastMCP(
    name="engram",
    version="4.0.0",
    instructions=(
        "Engram v4 MCP — thin proxy for the /api/v4 REST API. "
        "Read tools: search_entities, get_entity, list_recent, get_today, list_suggestions, get_agent_activity. "
        "Write tools: capture, create_entity, update_entity, link_entities, "
        "accept_suggestion, dismiss_suggestion, reconcile_suggestions, submit_candidates, append_activity_update. "
        "All tools are routed directly to /api/v4 endpoints."
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


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


@mcp.tool(description=(
    "Search v4 entities using Engram search. "
    "Supports hybrid, keyword, semantic, or tag-only retrieval. Read-only."
))
def search_entities(
    query: str = "",
    entity_type: Optional[str] = None,
    mode: str = "hybrid",
    status: Optional[str] = None,
    lifecycle: str = "active",
    tag: Optional[str] = None,
    limit: int = 10,
) -> str:
    limit = max(1, min(limit, 50))
    params = {"mode": mode or "hybrid", "limit": limit, "lifecycle": lifecycle or "active"}
    if query:
        params["q"] = query
    if entity_type:
        params["type"] = entity_type
    if status:
        params["status"] = status
    if tag:
        params["tag"] = tag
    payload = _api("GET", "/search", params=params)
    return format_search_results(payload, query or f"tag:{tag}")


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


@mcp.tool(description=(
    "Get today's workspace snapshot: follow-ups due today, blocked/waiting tasks, "
    "active projects without open tasks, recent notes, and pending AI suggestions. Read-only."
))
def get_today() -> str:
    payload = _api("GET", "/today")
    return format_today(payload)


@mcp.tool(description=(
    "List AI suggestions awaiting review. status must be 'pending', 'accepted', 'dismissed', or 'all'. "
    "Defaults to 'pending'. Read-only."
))
def list_suggestions(status: str = "pending") -> str:
    payload = _api("GET", "/suggestions", params={"status": status})
    return format_suggestions(payload)


@mcp.tool(description="List recent agent automation actions, suggestions, and failures. Read-only.")
def get_agent_activity(limit: int = 20) -> str:
    limit = max(1, min(limit, 100))
    payload = _api("GET", "/agent-activity", params={"limit": limit})
    return format_agent_activity(payload)


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------


@mcp.tool(description=(
    "Capture raw text as a note. Triggers server-side AI extraction, tagging, and entity reconciliation. "
    "Use this when you want the server to classify and structure the content. "
    "Returns the created note plus any entities and relationships that were auto-applied."
))
def capture(content: str, source: Optional[str] = None) -> str:
    body: dict = {"content": content}
    if source:
        body["source"] = source
    payload = _api("POST", "/capture", json=body)
    return format_capture_result(payload)


@mcp.tool(description=(
    "Create a classified entity directly, bypassing AI extraction. "
    "type must be one of: note, task, project, area, resource, person. "
    "tags is a list of lowercase tag name strings."
))
def create_entity(
    type: str,
    title: str,
    content: Optional[str] = None,
    tags: Optional[List[str]] = None,
    status: Optional[str] = None,
    due_at: Optional[str] = None,
    follow_up_at: Optional[str] = None,
) -> str:
    body: dict = {"type": type, "title": title}
    if content:
        body["content"] = content
    if tags is not None:
        body["tags"] = tags
    if status:
        body["status"] = status
    if due_at:
        body["due_at"] = due_at
    if follow_up_at:
        body["follow_up_at"] = follow_up_at
    payload = _api("POST", "/entities", json=body)
    return format_entity_write(payload)


@mcp.tool(description=(
    "Update fields on an existing entity. "
    "Writable: title, content, status, lifecycle, due_at, follow_up_at, tags. "
    "due_at and follow_up_at accept ISO 8601 strings or null to clear."
))
def update_entity(
    entity_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    status: Optional[str] = None,
    lifecycle: Optional[str] = None,
    due_at: Optional[str] = None,
    follow_up_at: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> str:
    body: dict = {}
    for key, val in [
        ("title", title),
        ("content", content),
        ("status", status),
        ("lifecycle", lifecycle),
        ("due_at", due_at),
        ("follow_up_at", follow_up_at),
    ]:
        if val is not None:
            body[key] = val
    if tags is not None:
        body["tags"] = tags
    if not body:
        return "No fields provided to update."
    payload = _api("PATCH", f"/entities/{entity_id}", json=body)
    return format_entity_write(payload)


@mcp.tool(description=(
    "Create a relationship between two entities. "
    "relationship_type must be one of: parent, related, derived_from, mentions, assigned_to, references, blocks."
))
def link_entities(
    source_id: str,
    target_id: str,
    relationship_type: str = "related",
    evidence: Optional[str] = None,
) -> str:
    body: dict = {"target_entity_id": target_id, "relationship_type": relationship_type}
    if evidence:
        body["evidence"] = evidence
    payload = _api("POST", f"/entities/{source_id}/relationships", json=body)
    return format_link(payload)


@mcp.tool(description="Accept a pending AI suggestion, creating the suggested entity or relationship.")
def accept_suggestion(suggestion_id: str) -> str:
    payload = _api("POST", f"/suggestions/{suggestion_id}/accept")
    return format_suggestion_action(payload, "accepted")


@mcp.tool(description="Dismiss a pending AI suggestion without acting on it.")
def dismiss_suggestion(suggestion_id: str) -> str:
    payload = _api("POST", f"/suggestions/{suggestion_id}/dismiss")
    return format_suggestion_action(payload, "dismissed")


@mcp.tool(description="Reconcile pending suggestions and expire ones that no longer apply.")
def reconcile_suggestions(limit: int = 100) -> str:
    limit = max(1, min(limit, 500))
    payload = _api("POST", "/suggestions/reconcile", params={"limit": limit})
    return format_suggestion_reconcile(payload)


@mcp.tool(description=(
    "Submit pre-extracted candidates for an existing note, bypassing the server-side LLM extraction step. "
    "Use this when you have already analyzed the note and can supply structured candidates — "
    "it skips the GPT-4o extraction call and runs deduplication + reconciliation only. "
    "note_id must refer to an existing note entity. "
    "tags: list of {name, confidence} objects. "
    "entities: list of {type, title, content?, due_at?, follow_up_at?, confidence, evidence?} objects. "
    "links: list of {target_type, title, relationship_type, confidence, evidence?} objects."
))
def submit_candidates(
    note_id: str,
    summary: Optional[str] = None,
    tags: Optional[List[dict]] = None,
    entities: Optional[List[dict]] = None,
    links: Optional[List[dict]] = None,
) -> str:
    body: dict = {
        "summary": summary or "",
        "tags": tags or [],
        "entities": entities or [],
        "links": links or [],
    }
    payload = _api("POST", f"/entities/{note_id}/ingest_candidates", json=body)
    return format_capture_result(payload)


@mcp.tool(description="Append an activity update note to a project, task, or area. Used for summary context. Duplicate content within 24h is skipped; max 30 updates per entity.")
def append_activity_update(entity_id: str, content: str) -> str:
    payload = _api("POST", f"/entities/{entity_id}/activity_updates", json={"content": content})
    return format_activity_update(payload)


@mcp.tool(description=(
    "Mark a note as resolved, clearing it from the inbox. "
    "Sets ai_status to done so the note no longer appears in the inbox queue."
))
def resolve_note(entity_id: str) -> str:
    payload = _api("POST", f"/entities/{entity_id}/resolve")
    return format_entity_write(payload)


if __name__ == "__main__":
    transport = os.getenv("TRANSPORT", "stdio")
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host="127.0.0.1", port=int(os.getenv("MCP_PORT", 8765)))
