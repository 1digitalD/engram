# Engram v2 — API Specification
> All routes under `/api/v1`. JSON in, JSON out. Errors: `{"error": "message"}`.

---

## Conventions

**Entity response shape** (all entity endpoints return this):
```json
{
  "id": "uuid",
  "type": "note|task|project|area|resource|person",
  "title": "string|null",
  "content": "string|null",
  "status": "string",
  "lifecycle": "active|paused|done|archived|deleted",
  "follow_up_at": "ISO8601|null",
  "source": "string|null",
  "reference_url": "string|null",
  "properties": {},
  "ai_meta": {},
  "ai_status": "pending|processing|done|failed|skipped",
  "tag_ids": ["uuid"],
  "tags": [{"id": "uuid", "name": "string", "color": "string|null"}],
  "link_count": 0,
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

**List response shape:**
```json
{
  "data": [<entity>],
  "total": 0,
  "limit": 50,
  "offset": 0
}
```

**Backward-compat aliases** (Cycle 1 — removed in Cycle 2):
- `note.raw_text` → alias for `content`
- `note.is_archived` → alias for `lifecycle == 'archived'`
- `project.name` → alias for `title`
- `project.is_archived` → alias for `lifecycle == 'archived'`
- `task.due_date` → alias for `follow_up_at`

---

## Notes

### `GET /notes`
List notes.

Query params: `bucket`, `project_id`, `project_ids` (comma-sep), `area_id`, `tag_id`, `archived=false`, `limit=50`, `offset=0`

### `POST /notes`
Create a note. Routes through AI pipeline when `classify=true` (default).

Body:
```json
{
  "content": "string (required)",
  "classify": true,
  "bucket": "INBOX|PROJECTS|AREAS|RESOURCES|ARCHIVES",
  "project_id": "uuid",
  "area_id": "uuid",
  "person_id": "uuid",
  "tag_ids": ["uuid"],
  "source": "string"
}
```

Response `201`: `{"data": <entity>, "ai_status": "pending", "jobs": ["classify","embed"]}`

Note is returned immediately. AI classification is async.

### `GET /notes/:id`
### `PATCH /notes/:id`
Body: any subset of create fields. `"classify": true` triggers re-classification job.
### `DELETE /notes/:id`
Query: `cascade=false`. Returns `{"deleted": ["id"], "safe_to_cascade": [], "blocked": []}` when `cascade=false` (preview). Set `cascade=true` to execute.

---

## Tasks

### `GET /tasks`
Query: `status`, `project_id`, `area_id`, `note_id`, `limit=50`, `offset=0`

### `POST /tasks`
```json
{
  "title": "string (required)",
  "content": "string",
  "priority": "low|medium|high|urgent",
  "follow_up_at": "ISO8601",
  "project_id": "uuid",
  "area_id": "uuid",
  "note_id": "uuid"
}
```

### `GET /tasks/:id`
### `PATCH /tasks/:id`
### `DELETE /tasks/:id`

### `PATCH /tasks/:id/status`
Explicit status transition endpoint. Validates via state machine.
```json
{"status": "in_progress", "reason": "optional string"}
```
Returns `400` with `{"error": "invalid transition: pending → archived"}` on invalid transition.

---

## Projects

### `GET /projects`
Query: `archived=false`, `area_id`, `limit=50`, `offset=0`

### `POST /projects`
```json
{
  "title": "string (required)",
  "content": "string",
  "priority": "low|medium|high|urgent",
  "follow_up_at": "ISO8601",
  "area_id": "uuid",
  "color": "#hex"
}
```

### `GET /projects/:id`
Query: `include_notes=false`, `include_tasks=false`
### `PATCH /projects/:id`
### `DELETE /projects/:id`
### `PATCH /projects/:id/status`

---

## Areas

### `GET /areas`
### `POST /areas`
```json
{"title": "string (required)", "content": "string", "color": "#hex"}
```
### `GET /areas/:id`
### `PATCH /areas/:id`
### `DELETE /areas/:id`

---

## Resources

### `GET /resources`
Query: `resource_type`, `area_id`, `is_read`, `limit=50`, `offset=0`

### `POST /resources`
```json
{
  "title": "string (required)",
  "content": "string",
  "reference_url": "string",
  "source": "string",
  "properties": {
    "resource_type": "article|book|url|video|paper|tool|other",
    "author": "string",
    "is_read": false,
    "rating": 0
  },
  "area_id": "uuid",
  "tag_ids": ["uuid"]
}
```

### `GET /resources/:id`
### `PATCH /resources/:id`
### `DELETE /resources/:id`

---

## People

### `GET /people`
### `POST /people`
```json
{
  "title": "string (required, person's name)",
  "content": "string (notes about person)",
  "properties": {
    "email": "string",
    "external_ids": {},
    "last_contacted_at": "ISO8601"
  }
}
```
### `GET /people/:id`
### `PATCH /people/:id`
### `DELETE /people/:id`

---

## Tags

### `GET /tags`
### `POST /tags`
```json
{"name": "string (required)", "color": "#hex"}
```
### `GET /tags/:id`
### `PATCH /tags/:id`
### `DELETE /tags/:id`

---

## Entity Links (NEW in Cycle 2)

### `GET /entities/:id/links`
Returns all links for an entity (src or dst).

Query: `link_type`, `direction=both|outgoing|incoming`

Response:
```json
{
  "outgoing": [{"id": "uuid", "dst_id": "uuid", "dst_entity": <entity>, "link_type": "related", "source": "manual", "confidence": null}],
  "incoming": [{"id": "uuid", "src_id": "uuid", "src_entity": <entity>, "link_type": "related", "source": "ai", "confidence": 0.87}]
}
```

### `POST /entity-links`
```json
{
  "src_id": "uuid (required)",
  "dst_id": "uuid (required)",
  "link_type": "related|parent|references|blocks|mentions|derived_from|assigned_to",
  "evidence": "string"
}
```
Returns `409` if link already exists. Returns `400` if src already has a parent (for `link_type=parent`).

### `DELETE /entity-links/:id`

### `GET /entities/:id/delete-preview`
Returns orphan analysis before deletion.
```json
{
  "entity": <entity>,
  "safe_to_cascade": [<entity>],
  "blocked": [<entity>],
  "warning": "2 linked entities will also be deleted"
}
```

---

## Search

### `GET /search`
Query: `q` (required), `limit=20`, `mode=hybrid|fts|semantic`, `type` (filter), `lifecycle=active`

Response:
```json
{
  "data": [<entity>],
  "query": "string",
  "count": 0,
  "mode": "hybrid"
}
```

### `GET /entities/:id/related`
Proactive surfacing — semantically similar entities not already linked.
Query: `limit=5`, `types=note,resource` (filter)

---

## Ingestion (multi-modal capture)

### `POST /ingest`
Multi-modal capture. Returns immediately; AI processing is async.
```json
{
  "content": "string",
  "media_url": "string",
  "media_type": "image|pdf|audio|url",
  "media_base64": "string",
  "media_mime": "string",
  "source": "string"
}
```
Response `201`: `{"data": <entity>, "ai_status": "pending"}`

---

## Daily Notes

### `GET /daily`
Query: `date=YYYY-MM-DD` (default: today)
Returns or creates a daily note entity.

### `POST /daily/append`
```json
{"content": "string to append"}
```

---

## Jobs (internal / debug)

### `GET /jobs`
Query: `status=pending|running|done|failed`, `entity_id`, `limit=50`

### `POST /jobs/:id/retry`
Force-retry a failed job immediately.

---

## Entity Events (audit log)

### `GET /entities/:id/events`
Returns event history for an entity.
Query: `limit=50`, `event_type`, `actor`

Response:
```json
{
  "data": [{
    "id": "uuid",
    "event_type": "status_changed",
    "actor": "user",
    "old_value": {"status": "pending"},
    "new_value": {"status": "in_progress"},
    "confidence": null,
    "reason": null,
    "created_at": "ISO8601"
  }]
}
```

---

## Summaries (unchanged)

### `GET /summaries`
### `POST /summaries/generate`
### `GET /summaries/:id`

---

## Review

### `GET /review/weekly-digest`

---

## Batch

### `POST /batch`
```json
{
  "operations": [
    {"method": "POST", "path": "/notes", "body": {}},
    {"method": "PATCH", "path": "/tasks/:id", "body": {}}
  ],
  "atomic": false
}
```
