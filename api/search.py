"""Unified search endpoint — hybrid/FTS/semantic across all entity types."""

from flask import request, jsonify
from api import api_bp
from services.search import search


@api_bp.route("/search", methods=["GET"])
def search_endpoint():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"data": [], "query": "", "count": 0, "mode": request.args.get("mode", "hybrid")})

    limit = request.args.get("limit", 20, type=int)
    mode = request.args.get("mode", "hybrid")

    filters = {}
    if request.args.get("type"):
        filters["type"] = request.args["type"]
    if request.args.get("status"):
        filters["status"] = request.args["status"]
    if request.args.get("lifecycle"):
        filters["lifecycle"] = request.args["lifecycle"]

    results = search(q, limit=limit, mode=mode, filters=filters)
    data = [e.to_dict() for e in results]

    return jsonify({
        "data": data,
        "query": q,
        "count": len(data),
        "mode": mode,
    })
