from flask import request, jsonify
from api import api_bp
import logging

logger = logging.getLogger(__name__)


@api_bp.route("/ingest", methods=["POST"])
def ingest():
    """
    Smart multi-modal ingestion endpoint.
    Accepts text, images (base64), PDFs (base64 or URL), audio (URL), and web URLs.
    Runs full extraction + entity resolution pipeline.

    Body (JSON):
      content      str   - raw text (required if no media)
      source       str   - origin: discord | web | api | hermes (default: api)
      media_url    str   - URL to image, PDF, audio, or web page
      media_type   str   - image | pdf | audio | url
      media_base64 str   - base64-encoded file content (alternative to media_url)
      media_mime   str   - MIME type for base64 content (default: image/jpeg)

    Returns:
      note         dict  - created note
      tasks        list  - created tasks
      people       list  - resolved/created people
      project      dict  - matched/created project (or null)
      area         dict  - matched/created area (or null)
      confident    bool  - whether confidence threshold was met
      extraction   dict  - AI classification summary
    """
    data = request.get_json(silent=True) or {}

    content = data.get("content", "").strip()
    media_url = data.get("media_url")
    media_type = data.get("media_type")
    media_base64 = data.get("media_base64")
    media_mime = data.get("media_mime", "image/jpeg")
    source = data.get("source", "api")

    if not content and not media_url and not media_base64:
        return jsonify({"error": "content, media_url, or media_base64 is required"}), 400

    try:
        from services.ingestion import run_ingestion
        result = run_ingestion(
            content=content,
            media_url=media_url,
            media_type=media_type,
            media_base64=media_base64,
            media_mime=media_mime,
            source=source,
        )
        if "error" in result:
            return jsonify(result), 400

        return jsonify(result), 201

    except Exception as e:
        logger.exception(f"Ingestion failed: {e}")
        return jsonify({"error": str(e)}), 500
