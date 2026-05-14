"""Background summarization jobs (HTTP trigger + status)."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime

from flask import current_app, jsonify, request

from api import api_bp
from api.summaries import _parse_granularity
from services.summarizer import Summarizer

_jobs_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def _set_job_state(job_id: str, **kwargs):
    with _jobs_lock:
        state = _jobs.setdefault(job_id, {})
        state.update(kwargs)
        _jobs[job_id] = state


def _run_job(app, granularity: str, area_id: str | None, job_id: str):
    with app.app_context():
        try:
            _set_job_state(
                job_id,
                state="running",
                message=None,
                started_at=datetime.utcnow().isoformat() + "Z",
                finished_at=None,
                summaries_created=0,
                granularity=granularity,
                area_id=area_id,
            )
            count = Summarizer().execute_scheduled_summarization(
                granularity, area_id=area_id
            )
            _set_job_state(
                job_id,
                state="completed",
                finished_at=datetime.utcnow().isoformat() + "Z",
                summaries_created=count,
                message=None,
            )
        except Exception as e:
            _set_job_state(
                job_id,
                state="error",
                finished_at=datetime.utcnow().isoformat() + "Z",
                message=str(e),
            )


@api_bp.route("/jobs/summarize", methods=["POST"])
def trigger_summarize_job():
    """
    Body: { granularity: str, area_id?: str }
    Enqueues async summarization over the last 7 days (all areas, or one area).
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    granularity_raw = data.get("granularity")
    if not granularity_raw or not isinstance(granularity_raw, str):
        return jsonify({"error": "granularity is required"}), 400

    gran = _parse_granularity(granularity_raw)
    if gran is None:
        return jsonify({"error": "invalid granularity"}), 400

    area_id = data.get("area_id")
    if area_id is not None and not isinstance(area_id, str):
        return jsonify({"error": "area_id must be a string"}), 400

    app = current_app._get_current_object()
    job_id = str(uuid.uuid4())

    if app.config.get("JOBS_SYNC"):
        _run_job(app, gran.value, area_id, job_id)
        with _jobs_lock:
            payload = dict(_jobs.get(job_id, {}))
        code = 200 if payload.get("state") != "error" else 500
        return jsonify({"data": {"job_id": job_id, "status": payload}}), code

    threading.Thread(
        target=_run_job,
        args=(app, gran.value, area_id, job_id),
        daemon=True,
    ).start()

    _set_job_state(
        job_id,
        state="queued",
        message=None,
        started_at=None,
        finished_at=None,
        summaries_created=0,
        granularity=gran.value,
        area_id=area_id,
    )
    return jsonify({"data": {"job_id": job_id, "accepted": True}}), 202


@api_bp.route("/jobs/status", methods=["GET"])
def job_status():
    job_id = request.args.get("job_id")
    with _jobs_lock:
        if job_id:
            state = _jobs.get(job_id, {"state": "unknown"})
        else:
            state = dict(_jobs)
        return jsonify({"data": state}), 200
