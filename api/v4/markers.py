"""Engram v4 follow-up markers API."""

from flask import jsonify, request

from api import api_v4_bp
from api.v4._shared import _error
from services import v4_markers as markers_service


@api_v4_bp.route("/markers", methods=["GET"])
def list_markers():
    entity_id = request.args.get("entity_id")
    rows = markers_service.list_markers(entity_id=entity_id)
    return jsonify({"data": [row.to_dict() for row in rows]})


@api_v4_bp.route("/markers/<marker_id>", methods=["GET"])
def get_marker(marker_id):
    marker = markers_service.get_marker(marker_id)
    if marker is None:
        return _error("marker not found", 404)
    return jsonify({"data": marker.to_dict()})


@api_v4_bp.route("/markers", methods=["POST"])
def create_marker():
    data = request.get_json(silent=True) or {}
    try:
        marker = markers_service.create_marker(data)
    except LookupError as exc:
        return _error(str(exc), 404)
    except ValueError as exc:
        return _error(str(exc), 400)
    return jsonify({"data": marker.to_dict()}), 201


@api_v4_bp.route("/markers/<marker_id>", methods=["PATCH"])
def update_marker(marker_id):
    data = request.get_json(silent=True) or {}
    try:
        marker = markers_service.update_marker(marker_id, data)
    except LookupError as exc:
        return _error(str(exc), 404)
    except ValueError as exc:
        return _error(str(exc), 400)
    return jsonify({"data": marker.to_dict()})


@api_v4_bp.route("/markers/<marker_id>", methods=["DELETE"])
def delete_marker(marker_id):
    try:
        markers_service.delete_marker(marker_id)
    except LookupError as exc:
        return _error(str(exc), 404)
    return jsonify({"data": {"id": marker_id, "deleted": True}})
