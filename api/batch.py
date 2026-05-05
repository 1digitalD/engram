"""
Batch operations endpoint.
Agents can submit multiple operations in a single request.
Each operation is: { "op": "GET|POST|PATCH|DELETE", "path": "/notes/...", "body": {} }
"""
from flask import request, jsonify
from api import api_bp
import logging

logger = logging.getLogger(__name__)


@api_bp.route("/batch", methods=["POST"])
def batch():
    """
    Execute multiple API operations in one request.

    Body:
      operations  list  - array of { op, path, body? }
      atomic      bool  - if true, rollback all on any failure (default: false)

    Each operation:
      op    str  - GET | POST | PATCH | DELETE
      path  str  - API path relative to /api/v1 (e.g. "/notes/abc")
      body  dict - request body for POST/PATCH

    Returns:
      results  list  - per-operation { status, data, error }
      success  bool  - true if all operations succeeded
    """
    data = request.get_json(silent=True) or {}
    operations = data.get("operations", [])
    atomic = data.get("atomic", False)

    if not operations:
        return jsonify({"error": "operations list is required"}), 400

    if len(operations) > 50:
        return jsonify({"error": "max 50 operations per batch"}), 400

    from flask import current_app
    from extensions import db

    results = []
    had_error = False

    with current_app.test_client() as client:
        for i, op in enumerate(operations):
            method = (op.get("op") or "GET").upper()
            path = op.get("path", "")
            body = op.get("body")

            if not path.startswith("/"):
                path = "/" + path

            full_path = f"/api/v1{path}"

            try:
                kwargs = {
                    "content_type": "application/json",
                    "headers": {"X-Batch": "true"},
                }
                if body:
                    import json
                    kwargs["data"] = json.dumps(body)

                if method == "GET":
                    resp = client.get(full_path, **kwargs)
                elif method == "POST":
                    resp = client.post(full_path, **kwargs)
                elif method == "PATCH":
                    resp = client.patch(full_path, **kwargs)
                elif method == "PUT":
                    resp = client.put(full_path, **kwargs)
                elif method == "DELETE":
                    resp = client.delete(full_path, **kwargs)
                else:
                    results.append({"index": i, "status": 400, "error": f"unsupported method: {method}"})
                    had_error = True
                    continue

                resp_data = resp.get_json()
                results.append({
                    "index": i,
                    "status": resp.status_code,
                    "data": resp_data,
                    "error": resp_data.get("error") if resp.status_code >= 400 else None,
                })

                if resp.status_code >= 400:
                    had_error = True
                    if atomic:
                        break

            except Exception as e:
                logger.error(f"Batch op {i} failed: {e}")
                results.append({"index": i, "status": 500, "error": str(e)})
                had_error = True
                if atomic:
                    break

    if atomic and had_error:
        try:
            db.session.rollback()
        except Exception:
            pass

    return jsonify({
        "results": results,
        "success": not had_error,
        "count": len(results),
    }), 200 if not had_error else 207
