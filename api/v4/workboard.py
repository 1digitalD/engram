"""Engram v4 workboard API."""

from flask import jsonify, request

from api import api_v4_bp
from services.v4_workboard import get_workboard


def _state_filters():
    values = []
    for raw in request.args.getlist("state"):
        for value in str(raw).split(","):
            cleaned = value.strip()
            if cleaned:
                values.append(cleaned)
    return values


@api_v4_bp.route("/workboard", methods=["GET"])
def workboard():
    group = request.args.get("group", "space")
    try:
        payload = get_workboard(group=group, state_filters=_state_filters())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"data": {"groups": payload["groups"]}, "meta": payload["meta"]})
