import logging
import os

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from config import config
from extensions import db
from models import init_fts

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

    # Init extensions
    db.init_app(app)

    # Register API blueprints
    from api import api_bp
    app.register_blueprint(api_bp)

    # ─── CLI Commands ──────────────────────────────────────────────────────

    @app.cli.command("init-db")
    def init_db():
        """Create all tables and FTS."""
        with app.app_context():
            db.create_all()
            try:
                init_fts()
                print("Tables + FTS created.")
            except Exception as e:
                print(f"FTS init warning (may already exist): {e}")

    # ─── Health Check ───────────────────────────────────────────────────────

    @app.route("/health")
    def health():
        status = {"db": "ok", "ai": "unknown"}
        try:
            db.session.execute(db.text("SELECT 1"))
        except Exception:
            status["db"] = "error"

        try:
            if os.getenv("OPENAI_API_KEY"):
                status["ai"] = "configured"
            else:
                status["ai"] = "missing_key"
        except Exception:
            status["ai"] = "error"

        return jsonify(status)

    # ─── React UI (SPA) ─────────────────────────────────────────────────────

    @app.route("/")
    def serve_react_app():
        return send_from_directory("static", "index.html")

    @app.route("/<path:filename>")
    def serve_static(filename):
        return send_from_directory("static", filename)

    # ─── Error Handlers ─────────────────────────────────────────────────────

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "not found"}), 404
        return send_from_directory("static", "index.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Server error: {e}")
        if request.path.startswith("/api/"):
            return jsonify({"error": "internal server error"}), 500
        return send_from_directory("static", "index.html"), 500

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
