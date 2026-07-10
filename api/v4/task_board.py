"""Engram v4 task board API."""

from flask import jsonify, request

from api import api_v4_bp
from services.v4_task_board import get_task_board, parse_date_param


def _status_filters():
    values = []
    for raw in request.args.getlist("status"):
        for value in str(raw).split(","):
            cleaned = value.strip()
            if cleaned:
                values.append(cleaned)
    return values


@api_v4_bp.route("/task-board", methods=["GET"])
def task_board():
    try:
        payload = get_task_board(
            status_filters=_status_filters(),
            assignee=request.args.get("assignee") or None,
            due_before=parse_date_param(request.args.get("due_before")),
            due_after=parse_date_param(request.args.get("due_after")),
            follow_up_before=parse_date_param(request.args.get("follow_up_before")),
            follow_up_after=parse_date_param(request.args.get("follow_up_after")),
            sort=request.args.get("sort", "created_at"),
            order=request.args.get("order"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"data": {"groups": payload["groups"]}, "meta": payload["meta"]})
