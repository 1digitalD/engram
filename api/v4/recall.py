"""Engram v4 recall API."""

from api import api_v4_bp
from api import v4_entities as _v4e
from api.v4._shared import *

@api_v4_bp.route("/entities/mentions", methods=["GET"])
def entity_mentions():
    """Lightweight, fast lookup for inline @-mention / [[link]] pickers.

    Returns active entities grouped by type, title-matching `q` (or most
    recently updated if `q` is empty), so the editor can show a live list
    while the user is still typing.
    """
    q = (request.args.get("q") or "").strip()
    limit_per_type = max(1, min(request.args.get("limit", MENTION_TYPES_PER_GROUP, type=int), 20))
    types_param = request.args.get("types")
    types = [t for t in (types_param.split(",") if types_param else ENTITY_TYPES) if t in ENTITY_TYPES]

    results = {}
    for entity_type in types:
        query = Entity.query.filter(Entity.type == entity_type, Entity.lifecycle == "active")
        if q:
            query = query.filter(Entity.title.ilike(f"%{q}%"))
        rows = query.order_by(Entity.updated_at.desc()).limit(limit_per_type).all()
        if rows:
            results[entity_type] = [
                {"id": row.id, "type": row.type, "title": row.title, "path": f"/{ENTITY_TYPE_PLURAL[row.type]}/{row.id}"}
                for row in rows
            ]
    return jsonify({"query": q, "results": results})


@api_v4_bp.route("/search", methods=["GET"])
def search():
    q = request.args.get("q", "").strip()
    tag = (request.args.get("tag") or "").strip().lower() or None
    if not q and not tag:
        return _error("either q or tag parameter is required")
    mode = request.args.get("mode", "hybrid")
    entity_type = request.args.get("type")
    status = request.args.get("status")
    lifecycle = request.args.get("lifecycle", "active")
    limit = request.args.get("limit", 20, type=int)

    if entity_type and entity_type not in ENTITY_TYPES:
        return _error(f"invalid entity type: {entity_type}")
    if lifecycle and lifecycle not in VALID_LIFECYCLE:
        return _error(f"invalid lifecycle: {lifecycle}")

    from services.v4_search import search_entities, list_by_tag
    if not q and tag:
        results = list_by_tag(
            tag,
            entity_type=entity_type,
            status=status,
            lifecycle=lifecycle,
            limit=limit,
        )
        results = _enrich_search_results_with_task_context(results)
        return jsonify({"query": "", "tag": tag, "mode": "tag", "results": results})

    results = search_entities(
        q,
        mode=mode,
        entity_type=entity_type,
        status=status,
        lifecycle=lifecycle,
        limit=limit,
        tag=tag,
    )
    results = _enrich_search_results_with_task_context(results)
    resolved_mode = mode if mode in {"keyword", "semantic", "hybrid"} else "hybrid"
    return jsonify({"query": q, "tag": tag, "mode": resolved_mode, "results": results})


@api_v4_bp.route("/ask", methods=["POST"])
def ask():
    """Answer a natural-language question from workspace context."""
    from services.v4_ask import ask_question

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return _error("question is required")

    try:
        top_k = max(1, min(int(data.get("top_k", 5)), 20))
    except (TypeError, ValueError):
        top_k = 5

    try:
        result = ask_question(question, top_k=top_k)
    except Exception as exc:
        logger.exception("ask failed: %s", exc)
        return _error("ask failed"), 500

    return jsonify(result)


