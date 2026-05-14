"""Universal entity API — unified CRUD across all entity types.

GET    /api/v2/entities/:id         — get any entity
PATCH  /api/v2/entities/:id         — update any entity
DELETE /api/v2/entities/:id         — delete any entity
GET    /api/v2/entities/:id/links   — get all links for entity
GET    /api/v2/entities/:id/events  — get events for entity
"""

from flask import request, jsonify
from api import api_v2_bp
from extensions import db
from models import Entity, EntityLink, EntityEvent
from services.entity_service import update_entity, delete_entity
import logging

logger = logging.getLogger(__name__)


@api_v2_bp.route("/entities/<entity_id>", methods=["GET"])
def v2_get_entity(entity_id):
    """Get any entity by ID."""
    entity = db.session.get(Entity, entity_id)
    if not entity:
        return jsonify({"error": "Entity not found"}), 404
    return jsonify({"data": entity.to_dict()})


@api_v2_bp.route("/entities/<entity_id>", methods=["PATCH"])
def v2_update_entity(entity_id):
    """Update any entity by ID."""
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "No fields to update"}), 400

    try:
        entity = update_entity(entity_id, data, actor="user")
        return jsonify({"data": entity.to_dict()})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Failed to update entity %s", entity_id)
        return jsonify({"error": str(e)}), 500


@api_v2_bp.route("/entities/<entity_id>", methods=["DELETE"])
def v2_delete_entity(entity_id):
    """Delete an entity with optional cascade."""
    cascade = request.args.get("cascade", "false").lower() == "true"
    try:
        result = delete_entity(entity_id, cascade_orphans=cascade)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Failed to delete entity %s", entity_id)
        return jsonify({"error": str(e)}), 500


@api_v2_bp.route("/entities/<entity_id>/links", methods=["GET"])
def v2_get_entity_links(entity_id):
    """Get all links (incoming + outgoing) for any entity."""
    entity = db.session.get(Entity, entity_id)
    if not entity:
        return jsonify({"error": "Entity not found"}), 404

    outgoing = EntityLink.query.filter_by(src_id=entity_id).all()
    incoming = EntityLink.query.filter_by(dst_id=entity_id).all()

    def _enrich(link, direction):
        d = link.to_dict()
        d["direction"] = direction
        other_id = link.dst_id if direction == "outgoing" else link.src_id
        other = db.session.get(Entity, other_id)
        if other:
            d["src_type"] = link.src_entity.type if link.src_entity else None
            d["dst_type"] = link.dst_entity.type if link.dst_entity else None
            d["other_entity"] = {
                "id": other.id,
                "type": other.type,
                "title": other.title,
                "content": other.content,
            }
        return d

    return jsonify({
        "data": [_enrich(l, "outgoing") for l in outgoing] + [_enrich(l, "incoming") for l in incoming],
        "outgoing": [_enrich(l, "outgoing") for l in outgoing],
        "incoming": [_enrich(l, "incoming") for l in incoming],
    })


from services.search import grouped_search


@api_v2_bp.route("/entities/<entity_id>/extracted", methods=["GET"])
def v2_get_extracted_entities(entity_id):
    """Get entities extracted from a note plus pending suggestions.

    Returns:
      - derived: entities created from this note (derived_from links)
      - linked_existing: projects/areas matched and linked (related links)
      - suggestions: pending AiSuggestions for this note
    """
    entity = db.session.get(Entity, entity_id)
    if not entity:
        return jsonify({"error": "Entity not found"}), 404

    outgoing = EntityLink.query.filter_by(src_id=entity_id).all()
    incoming = EntityLink.query.filter_by(dst_id=entity_id).all()

    derived = []
    linked_existing = []
    for link in outgoing:
        other = db.session.get(Entity, link.dst_id)
        if not other:
            continue
        d = other.to_dict()
        d["link_type"] = link.link_type
        d["link_id"] = link.id
        if link.link_type == "derived_from":
            derived.append(d)
        elif link.link_type in ("related", "references", "parent"):
            if other.type in ("project", "area"):
                linked_existing.append(d)

    from models import AiSuggestion
    suggestions = AiSuggestion.query.filter_by(
        source_entity_id=entity_id,
        status="pending"
    ).order_by(AiSuggestion.created_at.desc()).limit(50).all()

    return jsonify({
        "data": {
            "derived": derived,
            "linked_existing": linked_existing,
            "suggestions": [s.to_dict() for s in suggestions],
        }
    })


@api_v2_bp.route("/entities/search", methods=["GET"])
def v2_search_entities():
    """Universal search grouped by entity type.

    Query params:
      q: search query (required)
      limit: max results per type (default 10, max 50)
      mode: 'hybrid' | 'fts' | 'semantic' (default 'hybrid')
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q parameter is required"}), 400

    limit = request.args.get("limit", 10, type=int)
    limit = max(1, min(limit, 50))
    mode = request.args.get("mode", "hybrid")
    if mode not in ("hybrid", "fts", "semantic"):
        mode = "hybrid"

    result = grouped_search(q, limit_per_type=limit, mode=mode)
    total = sum(len(v) for v in result.values())

    return jsonify({
        "data": result,
        "query": q,
        "total": total,
        "mode": mode,
    })


@api_v2_bp.route("/entities/<entity_id>/events", methods=["GET"])
def v2_get_entity_events(entity_id):
    """Get events for an entity."""
    entity = db.session.get(Entity, entity_id)
    if not entity:
        return jsonify({"error": "Entity not found"}), 404

    events = EntityEvent.query.filter_by(entity_id=entity_id)\
        .order_by(EntityEvent.created_at.desc())\
        .limit(100)\
        .all()

    return jsonify({
        "data": [e.to_dict() for e in events],
    })


@api_v2_bp.route("/today/summary", methods=["GET"])
def v2_today_summary():
    """Get today-view summary: projects needing attention and people with blocked tasks.

    Returns:
      - projects_without_next_action: active projects with no pending/in_progress tasks
      - waiting_on_people: people who have tasks assigned where status is 'waiting'/'blocked'
    """
    from models import EntityLink

    project_ids_with_action = set()
    task_links = EntityLink.query.filter(
        EntityLink.link_type == "parent",
        EntityLink.src_id.in_(
            db.session.query(Entity.id).filter(Entity.type == "task", Entity.lifecycle == "active")
        )
    ).all()
    for link in task_links:
        project_ids_with_action.add(link.dst_id)

    active_projects = Entity.query.filter(
        Entity.type == "project",
        Entity.lifecycle == "active"
    ).all()
    projects_without_next_action = [
        p.to_dict() for p in active_projects if p.id not in project_ids_with_action
    ]

    person_ids_with_waiting = set()
    assigned_links = EntityLink.query.filter_by(link_type="assigned_to").all()
    for link in assigned_links:
        task = db.session.get(Entity, link.src_id)
        if task and task.type == "task" and task.lifecycle == "active" and task.status in ("waiting", "blocked"):
            person_ids_with_waiting.add(link.dst_id)

    waiting_people = []
    for pid in person_ids_with_waiting:
        person = db.session.get(Entity, pid)
        if person and person.type == "person" and person.lifecycle == "active":
            d = person.to_dict()
            person_tasks = Entity.query.filter(
                Entity.type == "task",
                Entity.lifecycle == "active",
                Entity.id.in_(
                    db.session.query(EntityLink.src_id).filter(
                        EntityLink.dst_id == pid,
                        EntityLink.link_type == "assigned_to"
                    )
                )
            ).all()
            d["task_count"] = len(person_tasks)
            waiting_people.append(d)

    return jsonify({
        "data": {
            "projects_without_next_action": projects_without_next_action,
            "waiting_on_people": waiting_people,
        }
    })
