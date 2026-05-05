import logging
import os

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from config import config
from extensions import db, load_sqlite_extensions
from models import init_fts, init_vec

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

    # Load sqlite-vec extension on every connection (graceful if not installed)
    with app.app_context():
        load_sqlite_extensions(db)

    # Register API blueprint (includes all sub-modules)
    from api import api_bp
    app.register_blueprint(api_bp)

    # ── CLI Commands ──────────────────────────────────────────────────────────

    @app.cli.command("init-db")
    def init_db_cmd():
        """Create all tables, FTS5, and sqlite-vec virtual tables."""
        with app.app_context():
            db.create_all()
            try:
                init_fts()
                logger.info("FTS5 initialized.")
            except Exception as e:
                logger.warning(f"FTS5 init warning (may already exist): {e}")
            try:
                init_vec()
                logger.info("sqlite-vec initialized.")
            except Exception as e:
                logger.warning(f"sqlite-vec init warning: {e}")
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
        except Exception:
            status["db"] = "error"

        try:
            db.session.execute(db.text("SELECT * FROM vec_chunks LIMIT 1"))
            status["vec"] = "ok"
        except Exception:
            status["vec"] = "unavailable"

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


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
