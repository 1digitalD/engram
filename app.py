import logging
import os
import threading

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from config import config
from extensions import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.FileHandler("engram.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config[config_name])
    CORS(app)

    # Init DB
    db.init_app(app)

    # v4 clean cutover: only the canonical v4 API is registered at runtime.
    from api import api_v4_bp
    app.register_blueprint(api_v4_bp)

    # Start job worker on boot (non-blocking background thread)
    # Skip in testing mode to avoid background DB connections
    is_testing = app.config.get("TESTING", False)
    if not is_testing:
        def _start_worker():
            try:
                from services.job_worker import start_worker
                start_worker(app)
                logger.info("Job worker started")
            except Exception as e:
                logger.warning("Job worker failed to start: %s", e)

        with app.app_context():
            threading.Thread(target=_start_worker, daemon=True).start()
    else:
        logger.info("Skipping job worker (testing mode)")

    # ── CLI Commands ──────────────────────────────────────────────────────────

    @app.cli.command("init-db")
    def init_db_cmd():
        """Create all tables from SCHEMA.sql."""
        with app.app_context():
            db.create_all()
            print("Database ready.")

    @app.cli.command("embed-backfill")
    def embed_backfill_cmd():
        """Generate embeddings for all notes that are missing them."""
        with app.app_context():
            from services.embeddings import backfill_embeddings
            backfill_embeddings()

    # ── Health Check ─────────────────────────────────────────────────────────

    @app.route("/health")
    def health():
        status = {"db": "ok", "ai": "unknown", "vec": "unknown"}
        try:
            db.session.execute(db.text("SELECT 1"))
        except Exception as e:
            status["db"] = "error"
            logger.error("Health check DB probe failed: %s", e)

        try:
            db.session.execute(db.text("SELECT * FROM entity_chunks LIMIT 1"))
            status["vec"] = "ok"
        except Exception as e:
            status["vec"] = "unavailable"
            logger.warning("Health check vector probe failed: %s", e)

        if os.getenv("OPENAI_API_KEY"):
            status["ai"] = "configured"
        else:
            status["ai"] = "missing_key"

        return jsonify(status)

    # ── React SPA ─────────────────────────────────────────────────────────────
    # Serve static assets directly; fall through to index.html for SPA routes.

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path):
        import os as _os
        static_file = _os.path.join(app.static_folder or "static", path)
        if path and _os.path.isfile(static_file):
            return send_from_directory(app.static_folder or "static", path)
        return send_from_directory(app.static_folder or "static", "index.html")

    # ── Error Handlers ────────────────────────────────────────────────────────

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "not found"}), 404
        return send_from_directory(app.static_folder or "static", "index.html"), 200

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Server error: {e}")
        if request.path.startswith("/api/"):
            return jsonify({"error": "internal server error"}), 500
        return send_from_directory("static", "index.html"), 500

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
