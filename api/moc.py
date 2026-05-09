"""Maps of Content (MOC) generation API."""

from flask import jsonify, request

from api import api_bp
from extensions import db
from services.moc import generate_map_of_content


@api_bp.route("/moc/generate", methods=["POST"])
def moc_generate():
    """
    Body: { "note_ids": [str, ...] }
    Creates a new MOC note via Claude and ``child_of`` links from the MOC to each source note.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    note_ids = data.get("note_ids")
    if not isinstance(note_ids, list) or not note_ids:
        return jsonify({"error": "note_ids must be a non-empty list"}), 400

    try:
        note = generate_map_of_content(note_ids)
    except ValueError as e:
        msg = str(e)
        if msg.startswith("note not found:"):
            return jsonify({"error": msg}), 404
        return jsonify({"error": msg}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"moc generation failed: {e}"}), 502

    return jsonify({"data": note.to_dict()}), 201
