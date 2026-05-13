#!/usr/bin/env python3
"""
Engram MCP Server — exposes Engram as an MCP tool server for Claude,
Hermes, and any MCP-compatible agent.

Transport: STDIO (local) — run with: python mcp/server.py
Streamable HTTP: uvicorn mcp.server:mcp_app --port 8765 (set TRANSPORT=http)

Tools:
  capture          — ingest any content (text/image/pdf/audio/url)
  search           — hybrid semantic + FTS search (notes)
  search_entities  — unified search across all entity types
  get_note         — fetch a single note with backlinks
  get_entity       — fetch any entity by ID
  list_recent      — inbox, recent notes, due tasks
  update_note      — edit, re-route, or archive a note
  update_entity    — update any entity by ID
  create_entity    — create any entity type
  link_notes       — create explicit knowledge graph link
  review           — daily/weekly digest of items needing attention
"""
import os
import sys
import json
import httpx
from typing import Optional

# Add parent dir so we can import shared types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from fastmcp import FastMCP
except ImportError:
    print("fastmcp not installed. Run: pip install fastmcp", file=sys.stderr)
    sys.exit(1)

# Default base: v2 API. Tools that need v1-only endpoints use full paths.
ENGRAM_BASE = os.getenv("ENGRAM_API_BASE", "http://localhost:5001/api/v2")
ENGRAM_V1_BASE = os.getenv("ENGRAM_API_V1_BASE", "http://localhost:5001/api/v1")
ENGRAM_TIMEOUT = float(os.getenv("ENGRAM_API_TIMEOUT", "60"))

mcp = FastMCP(
    name="engram",
    version="2.0.0",
    instructions=(
        "Engram is your personal knowledge management system. "
        "Use `capture` to store any information. Use `search` to find notes. "
        "Use `review` to get a digest of what needs attention. "
        "Notes are organized by PARA: Projects, Areas, Resources, Archives."
    ),
)


# ── HTTP client ───────────────────────────────────────────────────────────────

def _api(method: str, path: str, base: Optional[str] = None, **kwargs) -> dict:
    """Make a request to the Engram API with clearer failure modes for MCP clients."""
    api_base = base or ENGRAM_BASE
    # If path starts with /api/, treat it as absolute (already has version prefix)
    if path.startswith("/api/"):
        # Extract the origin (e.g., http://localhost:5001) from api_base
        if "://" in api_base:
            origin = api_base.rsplit("/api/", 1)[0]
        else:
            origin = "http://localhost:5001"
        url = f"{origin}{path}"
    else:
        url = f"{api_base}{path}"
    try:
        with httpx.Client(timeout=ENGRAM_TIMEOUT) as client:
            resp = getattr(client, method.lower())(url, **kwargs)
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError as e:
        raise RuntimeError(
            f"Engram API is unreachable at {api_base}. Start the app first, for example: PORT=5001 flask run"
        ) from e
    except httpx.TimeoutException as e:
        raise RuntimeError(f"Engram API timed out after {ENGRAM_TIMEOUT:.0f}s calling {path}") from e
    except httpx.HTTPStatusError as e:
        body = e.response.text.strip()
        detail = f": {body[:300]}" if body else ""
        raise RuntimeError(f"Engram API {e.response.status_code} for {path}{detail}") from e


mcp_app = mcp.http_app(path="/mcp", transport="streamable-http")


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool(
    description=(
        "Capture any information into Engram. Automatically classifies, extracts tasks/people/tags, "
        "and routes to the right PARA bucket. Supports text, images (base64), PDFs (base64 or URL), "
        "audio (URL), and web URLs."
    )
)
def capture(
    content: str = "",
    source: str = "mcp",
    media_url: Optional[str] = None,
    media_type: Optional[str] = None,
    media_base64: Optional[str] = None,
    media_mime: Optional[str] = None,
) -> str:
    """
    Ingest content into Engram.
    - content: text to capture (required if no media)
    - source: origin identifier (mcp, discord, web, etc.)
    - media_url: URL to image, PDF, audio, or web page
    - media_type: image | pdf | audio | url
    - media_base64: base64-encoded file (alternative to media_url)
    - media_mime: MIME type for base64 (default: image/jpeg)
    """
    payload = {"content": content, "source": source}
    if media_url:
        payload["media_url"] = media_url
    if media_type:
        payload["media_type"] = media_type
    if media_base64:
        payload["media_base64"] = media_base64
    if media_mime:
        payload["media_mime"] = media_mime

    result = _api("POST", "/api/v1/ingest", json=payload, base=ENGRAM_V1_BASE)

    note = result.get("note", {})
    extraction = result.get("extraction", {})
    tasks = result.get("tasks", [])
    people = result.get("people", [])
    project = result.get("project")
    area = result.get("area")
    confident = result.get("confident", False)

    lines = [
        f"**Captured** (confidence: {extraction.get('confidence', 0):.0%})",
        f"- Note ID: `{note.get('id', '?')}`",
        f"- Bucket: {note.get('bucket', '?')}",
        f"- Summary: {extraction.get('summary', '')}",
        f"- Reasoning: {extraction.get('reasoning', '')}",
    ]
    if project:
        lines.append(f"- Project: {project.get('name')}")
    if area:
        lines.append(f"- Area: {area.get('name')}")
    if tasks:
        lines.append(f"- Tasks created: {len(tasks)}")
        for t in tasks:
            lines.append(f"  - [ ] {t.get('title')} (due: {t.get('due_date') or 'none'})")
    if people:
        lines.append(f"- People: {', '.join(p.get('name', '') for p in people)}")
    if not confident:
        lines.append("- ⚠️ Low confidence — note placed in INBOX for manual review")

    return "\n".join(lines)


@mcp.tool(
    description=(
        "Search Engram notes using hybrid semantic + keyword search. "
        "Returns the most relevant notes for your query."
    )
)
def search(
    query: str,
    mode: str = "hybrid",
    bucket: Optional[str] = None,
    project_id: Optional[str] = None,
    limit: int = 10,
) -> str:
    """
    Search notes.
    - query: search terms or natural language question
    - mode: hybrid (default) | fts | semantic
    - bucket: filter by INBOX | PROJECTS | AREAS | RESOURCES | ARCHIVES
    - project_id: filter to a specific project
    - limit: max results (default 10, max 50)
    """
    limit = min(limit, 50)
    params = {"q": query, "mode": mode, "limit": limit}
    if bucket:
        params["bucket"] = bucket.upper()
    if project_id:
        params["project_id"] = project_id

    result = _api("GET", "/api/v1/notes/search", params=params, base=ENGRAM_V1_BASE)
    notes = result.get("data", [])

    if not notes:
        return f"No results found for: {query}"

    lines = [f"**Search results** for '{query}' ({len(notes)} found, mode={mode})\n"]
    for i, note in enumerate(notes, 1):
        score = note.get("_score", "")
        score_str = f" [{score:.3f}]" if score else ""
        bucket_str = note.get("bucket", "")
        project = note.get("project", {}) or {}
        proj_str = f" · {project.get('name', '')}" if project else ""
        tags = ", ".join(note.get("tag_names", []))
        tag_str = f" · #{tags}" if tags else ""
        text_preview = note.get("raw_text", "")[:120].replace("\n", " ")
        lines.append(
            f"{i}. `{note['id']}`{score_str} [{bucket_str}{proj_str}{tag_str}]\n"
            f"   {text_preview}…"
        )

    return "\n".join(lines)


@mcp.tool(
    description="Retrieve a single note by ID, including its full text, metadata, and backlinks."
)
def get_note(
    note_id: str,
    include_links: bool = True,
) -> str:
    """
    Fetch a note by ID.
    - note_id: the note's UUID
    - include_links: whether to include backlinks and related notes
    """
    result = _api("GET", f"/api/v1/notes/{note_id}", base=ENGRAM_V1_BASE)
    note = result.get("data", {})
    if not note:
        return f"Note {note_id} not found."

    ai = note.get("ai_meta") or {}
    project = note.get("project") or {}
    area = note.get("area") or {}
    tags = note.get("tag_names", [])

    lines = [
        f"**Note** `{note['id']}`",
        f"- Bucket: {note.get('bucket')}",
        f"- Created: {note.get('created_at', '')[:10]}",
    ]
    if project:
        lines.append(f"- Project: {project.get('name')}")
    if area:
        lines.append(f"- Area: {area.get('name')}")
    if tags:
        lines.append(f"- Tags: {', '.join(tags)}")
    if ai.get("summary"):
        lines.append(f"- Summary: {ai['summary']}")
    if ai.get("confidence"):
        lines.append(f"- AI confidence: {ai['confidence']:.0%}")

    lines.append(f"\n**Content:**\n{note.get('raw_text', '')}")

    if include_links:
        links_result = _api("GET", f"/links/{note_id}")
        total_links = links_result.get("total", 0)
        if total_links:
            lines.append(f"\n**Links:** {total_links} connections")
            for link in (links_result.get("incoming", []) + links_result.get("outgoing", []))[:5]:
                other_id = link.get("dst_id") if link.get("src_id") == note_id else link.get("src_id")
                lines.append(f"  - [{link.get('link_type')}] `{other_id}` (weight: {link.get('weight', 1):.2f})")

    return "\n".join(lines)


@mcp.tool(
    description=(
        "List recent notes, inbox items, or due tasks. "
        "Use scope='inbox' for unprocessed notes, 'recent' for latest captures, "
        "'tasks' for pending/due tasks."
    )
)
def list_recent(
    scope: str = "inbox",
    limit: int = 10,
    project_id: Optional[str] = None,
) -> str:
    """
    List items needing attention.
    - scope: inbox | recent | tasks | all
    - limit: number of results (default 10)
    - project_id: filter tasks to a project
    """
    limit = min(limit, 50)
    lines = []

    if scope in ("inbox", "all"):
        result = _api("GET", "/api/v1/notes", params={"bucket": "INBOX", "limit": limit}, base=ENGRAM_V1_BASE)
        notes = result.get("data", [])
        lines.append(f"**Inbox** ({len(notes)} items):")
        for n in notes:
            lines.append(f"  - `{n['id']}` {n.get('raw_text', '')[:80]}…")

    if scope in ("recent", "all"):
        result = _api("GET", "/api/v1/notes", params={"limit": limit}, base=ENGRAM_V1_BASE)
        notes = result.get("data", [])
        lines.append(f"\n**Recent notes** ({len(notes)}):")
        for n in notes:
            lines.append(f"  - `{n['id']}` [{n.get('bucket')}] {n.get('raw_text', '')[:80]}…")

    if scope in ("tasks", "all"):
        params = {"status": "PENDING", "limit": limit}
        if project_id:
            params["project_id"] = project_id
        result = _api("GET", "/api/v1/tasks", params=params, base=ENGRAM_V1_BASE)
        tasks = result.get("data", [])
        lines.append(f"\n**Pending tasks** ({len(tasks)}):")
        for t in tasks:
            due = f" (due {t.get('due_date', '')[:10]})" if t.get("due_date") else ""
            proj = f" [{t.get('project', {}).get('name', '')}]" if t.get("project") else ""
            lines.append(f"  - [ ] `{t['id']}` {t.get('title')}{proj}{due}")

    return "\n".join(lines) if lines else "Nothing found."


@mcp.tool(
    description="Update a note: edit text, change bucket, link to project/area, archive, or re-classify."
)
def update_note(
    note_id: str,
    raw_text: Optional[str] = None,
    bucket: Optional[str] = None,
    project_id: Optional[str] = None,
    area_id: Optional[str] = None,
    is_archived: Optional[bool] = None,
    tag_names: Optional[list[str]] = None,
) -> str:
    """
    Patch a note.
    - note_id: UUID of the note to update
    - raw_text: new text content
    - bucket: INBOX | PROJECTS | AREAS | RESOURCES | ARCHIVES
    - project_id: link to project UUID
    - area_id: link to area UUID
    - is_archived: set archived status
    - tag_names: replace tags with this list
    """
    patch = {}
    if raw_text is not None:
        patch["raw_text"] = raw_text
    if bucket is not None:
        patch["bucket"] = bucket.upper()
    if project_id is not None:
        patch["project_id"] = project_id
    if area_id is not None:
        patch["area_id"] = area_id
    if is_archived is not None:
        patch["is_archived"] = is_archived
    if tag_names is not None:
        patch["tag_names"] = tag_names

    if not patch:
        return "No fields to update."

    result = _api("PATCH", f"/api/v1/notes/{note_id}", json=patch, base=ENGRAM_V1_BASE)
    note = result.get("data", {})
    return f"Updated note `{note.get('id')}`. Bucket: {note.get('bucket')}. Tags: {', '.join(note.get('tag_names', []))}."


@mcp.tool(
    description="Create an explicit link between two notes in the knowledge graph."
)
def link_notes(
    src_id: str,
    dst_id: str,
    link_type: str = "related",
) -> str:
    """
    Link two notes.
    - src_id: source note UUID
    - dst_id: destination note UUID
    - link_type: related | child_of | depends_on | see_also | mentions
    """
    result = _api("POST", "/entity-links", json={"src_id": src_id, "dst_id": dst_id, "link_type": link_type})
    link = result.get("data", {})
    return f"Linked `{src_id}` → `{dst_id}` as [{link_type}]. Link ID: `{link.get('id')}`."


@mcp.tool(
    description=(
        "Generate a review digest for daily, weekly, or project-level summaries. "
        "Returns inbox count, pending tasks, stale projects, and new connections."
    )
)
def review(scope: str = "daily") -> str:
    """
    Get a review digest.
    - scope: daily | weekly | project:<project_id>
    """
    lines = [f"**{scope.capitalize()} Review**\n"]

    # Inbox
    inbox = _api("GET", "/api/v1/notes", params={"bucket": "INBOX", "limit": 50}, base=ENGRAM_V1_BASE)
    inbox_count = inbox.get("total", 0)
    lines.append(f"**Inbox:** {inbox_count} unprocessed notes")
    for n in inbox.get("data", [])[:3]:
        lines.append(f"  - `{n['id']}` {n.get('raw_text', '')[:80]}…")

    # Pending tasks
    tasks = _api("GET", "/api/v1/tasks", params={"status": "PENDING", "limit": 50}, base=ENGRAM_V1_BASE)
    task_list = tasks.get("data", [])
    due_soon = [t for t in task_list if t.get("due_date")]
    lines.append(f"\n**Tasks:** {len(task_list)} pending, {len(due_soon)} with due dates")
    for t in due_soon[:5]:
        lines.append(f"  - [ ] {t.get('title')} (due {t.get('due_date', '')[:10]})")

    if scope == "weekly" or scope.startswith("project:"):
        # Projects overview
        projects = _api("GET", "/api/v1/projects", base=ENGRAM_V1_BASE)
        proj_list = projects.get("data", [])
        active = [p for p in proj_list if not p.get("is_archived")]
        lines.append(f"\n**Active Projects:** {len(active)}")
        for p in active[:8]:
            lines.append(f"  - {p.get('name')} ({p.get('note_count', 0)} notes, {p.get('task_count', 0)} tasks)")

    lines.append(
        "\n*Tip: Use `search` to find related notes, `update_note` to route inbox items, "
        "`capture` to log new information.*"
    )

    return "\n".join(lines)


# ── Unified Entity Tools (v2 API) ────────────────────────────────────────────

# Mapping of entity types to their v1 CRUD endpoints (v2 unified endpoint not yet available)
_ENTITY_ENDPOINTS = {
    "note": "/api/v1/notes",
    "task": "/api/v1/tasks",
    "project": "/api/v1/projects",
    "area": "/api/v1/areas",
    "resource": "/api/v1/resources",
    "person": "/api/v1/people",
}

VALID_ENTITY_TYPES = list(_ENTITY_ENDPOINTS.keys())


def _entity_endpoint(entity_type: str) -> str:
    """Get the CRUD endpoint for an entity type."""
    return _ENTITY_ENDPOINTS.get(entity_type, _ENTITY_ENDPOINTS["note"])


@mcp.tool(
    description=(
        "Create any entity type in Engram: note, task, project, area, resource, or person. "
        "Use 'note' for free-form content, 'task' for actionable items, 'project' for multi-step goals, "
        "'area' for ongoing responsibilities, 'resource' for reference material, 'person' for contacts."
    )
)
def create_entity(
    entity_type: str = "note",
    title: Optional[str] = None,
    content: Optional[str] = None,
    properties: Optional[dict] = None,
    tag_names: Optional[list[str]] = None,
    follow_up_at: Optional[str] = None,
) -> str:
    """
    Create a new entity.
    - entity_type: note | task | project | area | resource | person
    - title: entity title (required for task, project, area, resource, person)
    - content: body text or notes
    - properties: type-specific fields as JSON object
    - tag_names: list of tag strings
    - follow_up_at: ISO8601 datetime for follow-up
    """
    if entity_type not in VALID_ENTITY_TYPES:
        return f"Invalid entity_type: {entity_type}. Must be one of: {', '.join(VALID_ENTITY_TYPES)}"

    endpoint = _entity_endpoint(entity_type)

    # Build payload based on entity type
    if entity_type == "note":
        payload = {"content": content or title or "", "source": "mcp"}
        if properties:
            if properties.get("bucket"):
                payload["bucket"] = properties["bucket"].upper()
            if properties.get("area_id"):
                payload["area_id"] = properties["area_id"]
            if properties.get("project_id"):
                payload["project_id"] = properties["project_id"]
    elif entity_type == "task":
        if not title:
            return "Error: 'title' is required for task entities."
        payload = {"title": title}
        if content:
            payload["content"] = content
        if properties:
            for key in ("priority", "project_id", "area_id", "note_id"):
                if key in properties:
                    payload[key] = properties[key]
        if follow_up_at:
            payload["follow_up_at"] = follow_up_at
    elif entity_type == "project":
        if not title:
            return "Error: 'title' is required for project entities."
        payload = {"title": title}
        if content:
            payload["content"] = content
        if properties:
            for key in ("priority", "area_id", "color", "follow_up_at"):
                if key in properties:
                    payload[key] = properties[key]
        if follow_up_at:
            payload["follow_up_at"] = follow_up_at
    elif entity_type == "area":
        if not title:
            return "Error: 'title' is required for area entities."
        payload = {"title": title}
        if content:
            payload["content"] = content
        if properties and "color" in properties:
            payload["color"] = properties["color"]
    elif entity_type == "resource":
        if not title:
            return "Error: 'title' is required for resource entities."
        payload = {"title": title}
        if content:
            payload["content"] = content
        if properties:
            payload["properties"] = properties
        if properties and "area_id" in properties:
            payload["area_id"] = properties["area_id"]
    elif entity_type == "person":
        if not title:
            return "Error: 'title' is required for person entities."
        payload = {"title": title}
        if content:
            payload["content"] = content
        if properties:
            payload["properties"] = properties

    if tag_names:
        payload["tag_names"] = tag_names

    result = _api("POST", endpoint, json=payload, base=ENGRAM_V1_BASE)
    entity = result.get("data", {})

    lines = [
        f"**Created {entity_type}** `{entity.get('id', '?')}`",
        f"- Title: {entity.get('title') or entity.get('name', '')}",
        f"- Status: {entity.get('status', '')}",
        f"- Lifecycle: {entity.get('lifecycle', '')}",
    ]
    if entity.get("tag_names"):
        lines.append(f"- Tags: {', '.join(entity['tag_names'])}")
    if entity.get("ai_status"):
        lines.append(f"- AI status: {entity['ai_status']}")

    return "\n".join(lines)


@mcp.tool(
    description=(
        "Search across all entity types in Engram using keyword matching. "
        "Returns notes, tasks, projects, areas, resources, and people matching your query."
    )
)
def search_entities(
    query: str,
    entity_type: Optional[str] = None,
    limit: int = 20,
) -> str:
    """
    Search all entities.
    - query: search terms
    - entity_type: filter by type (note | task | project | area | resource | person), or None for all
    - limit: max results (default 20, max 50)
    """
    limit = min(limit, 50)
    lines = []

    # Search notes (has dedicated search endpoint)
    if entity_type is None or entity_type == "note":
        try:
            result = _api("GET", "/api/v1/notes/search", params={"q": query, "limit": limit}, base=ENGRAM_V1_BASE)
            notes = result.get("data", [])
            if notes:
                lines.append(f"**Notes** ({len(notes)} found):")
                for n in notes[:limit]:
                    preview = (n.get("raw_text") or n.get("content") or "")[:100].replace("\n", " ")
                    bucket = n.get("bucket", "")
                    lines.append(f"  - `{n['id']}` [{bucket}] {preview}…")
        except RuntimeError:
            pass  # Skip if endpoint unavailable

    # Search other entity types by listing and filtering
    for etype in VALID_ENTITY_TYPES:
        if etype == "note" or (entity_type is not None and entity_type != etype):
            continue
        try:
            endpoint = _entity_endpoint(etype)
            result = _api("GET", endpoint, params={"limit": 50}, base=ENGRAM_V1_BASE)
            entities = result.get("data", [])
            # Simple keyword filter
            matched = [
                e for e in entities
                if query.lower() in (e.get("title") or e.get("name") or "").lower()
                or query.lower() in (e.get("content") or "").lower()
            ]
            if matched:
                lines.append(f"\n**{etype.capitalize()}s** ({len(matched)} found):")
                for e in matched[:limit]:
                    title = e.get("title") or e.get("name", "")
                    lines.append(f"  - `{e['id']}` {title}")
        except RuntimeError:
            pass

    if not lines:
        return f"No entities found matching: {query}"

    return "\n".join(lines)


@mcp.tool(
    description=(
        "Fetch any entity by ID regardless of type. Returns the full entity record "
        "with metadata, tags, and links."
    )
)
def get_entity(
    entity_id: str,
) -> str:
    """
    Get an entity by ID.
    - entity_id: UUID of the entity
    """
    # Try each entity type endpoint until we find it
    for etype in VALID_ENTITY_TYPES:
        try:
            endpoint = _entity_endpoint(etype)
            result = _api("GET", f"{endpoint}/{entity_id}", base=ENGRAM_V1_BASE)
            entity = result.get("data", {})
            if entity:
                return _format_entity(entity, etype)
        except RuntimeError:
            continue

    return f"Entity `{entity_id}` not found."


def _format_entity(entity: dict, entity_type: str) -> str:
    """Format an entity for display."""
    title = entity.get("title") or entity.get("name") or "(untitled)"
    ai = entity.get("ai_meta") or {}
    tags = entity.get("tag_names", [])

    lines = [
        f"**{entity_type.capitalize()}** `{entity['id']}`",
        f"- Title: {title}",
        f"- Status: {entity.get('status', '')}",
        f"- Lifecycle: {entity.get('lifecycle', '')}",
        f"- Created: {entity.get('created_at', '')[:10] if entity.get('created_at') else ''}",
        f"- Updated: {entity.get('updated_at', '')[:10] if entity.get('updated_at') else ''}",
    ]
    if tags:
        lines.append(f"- Tags: {', '.join(tags)}")
    if ai.get("summary"):
        lines.append(f"- AI Summary: {ai['summary']}")
    if ai.get("confidence"):
        lines.append(f"- AI confidence: {ai['confidence']:.0%}")
    if entity.get("follow_up_at"):
        lines.append(f"- Follow-up: {entity['follow_up_at'][:10]}")

    content = entity.get("content") or entity.get("raw_text") or ""
    if content:
        lines.append(f"\n**Content:**\n{content[:500]}{'…' if len(content) > 500 else ''}")

    return "\n".join(lines)


@mcp.tool(
    description=(
        "Update any entity by ID. Supports notes, tasks, projects, areas, resources, and people. "
        "Only provide fields you want to change."
    )
)
def update_entity(
    entity_id: str,
    entity_type: str = "note",
    title: Optional[str] = None,
    content: Optional[str] = None,
    status: Optional[str] = None,
    lifecycle: Optional[str] = None,
    properties: Optional[dict] = None,
    tag_names: Optional[list[str]] = None,
    follow_up_at: Optional[str] = None,
) -> str:
    """
    Update an entity.
    - entity_id: UUID of the entity
    - entity_type: note | task | project | area | resource | person
    - title: new title
    - content: new body content
    - status: new status (type-dependent)
    - lifecycle: active | paused | done | archived | deleted
    - properties: type-specific fields to merge
    - tag_names: replace all tags with this list
    - follow_up_at: ISO8601 datetime for follow-up
    """
    if entity_type not in VALID_ENTITY_TYPES:
        return f"Invalid entity_type: {entity_type}. Must be one of: {', '.join(VALID_ENTITY_TYPES)}"

    endpoint = _entity_endpoint(entity_type)
    patch = {}

    # Map fields based on entity type
    if entity_type == "note":
        if content is not None:
            patch["raw_text"] = content
        if title is not None:
            patch["title"] = title
        if properties:
            if "bucket" in properties:
                patch["bucket"] = properties["bucket"].upper()
            if "area_id" in properties:
                patch["area_id"] = properties["area_id"]
            if "project_id" in properties:
                patch["project_id"] = properties["project_id"]
        if lifecycle is not None:
            patch["is_archived"] = lifecycle == "archived"
    else:
        if title is not None:
            patch["title"] = title
        if content is not None:
            patch["content"] = content
        if status is not None:
            patch["status"] = status.lower()
        if lifecycle is not None:
            patch["lifecycle"] = lifecycle.lower()
        if properties:
            patch["properties"] = properties
        if follow_up_at is not None:
            patch["follow_up_at"] = follow_up_at

    if tag_names is not None:
        patch["tag_names"] = tag_names

    if not patch:
        return "No fields to update."

    result = _api("PATCH", f"{endpoint}/{entity_id}", json=patch, base=ENGRAM_V1_BASE)
    entity = result.get("data", {})
    return f"Updated {entity_type} `{entity.get('id')}`. Title: {entity.get('title') or entity.get('name', '')}. Status: {entity.get('status', '')}."


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    transport = os.getenv("TRANSPORT", "stdio")
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        # Streamable HTTP for remote agents
        mcp.run(transport="streamable-http", host="0.0.0.0", port=int(os.getenv("MCP_PORT", 8765)))
