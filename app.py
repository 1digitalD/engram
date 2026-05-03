import logging
import os

from flask import Flask, jsonify, render_template, request
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
            import os
            if os.getenv("OPENAI_API_KEY"):
                status["ai"] = "configured"
            else:
                status["ai"] = "missing_key"
        except Exception:
            status["ai"] = "error"

        return jsonify(status)

    # ─── Web UI ─────────────────────────────────────────────────────────────

    @app.route("/inbox")
    def inbox():
        from models import Note, BucketType
        notes = Note.query.filter(Note.bucket == BucketType.INBOX).order_by(Note.modified_at.desc()).all()
        return render_template("notes/index.html", notes=notes, active_bucket="inbox")

    @app.route("/notes")
    def notes():
        from models import Note
        notes = Note.query.order_by(Note.modified_at.desc()).limit(100).all()
        return render_template("notes/index.html", notes=notes)

    @app.route("/projects")
    def projects():
        return render_template("projects/index.html")

    @app.route("/areas")
    def areas():
        return render_template("areas/index.html")

    @app.route("/people")
    def people():
        return render_template("people/index.html")

    @app.route("/tasks")
    def tasks():
        return render_template("tasks/index.html")

    @app.route("/review")
    def review():
        return render_template("review/index.html")

    @app.route("/")
    def index():
        from models import Note, Project, Task, TaskStatus, BucketType
        inbox_count = Note.query.filter(Note.bucket == BucketType.INBOX).count()
        recent_notes = Note.query.order_by(Note.modified_at.desc()).limit(5).all()
        active_projects = Project.query.filter(Project.is_archived == False).limit(5).all()
        pending_tasks = Task.query.filter(Task.status != TaskStatus.DONE).count()
        return render_template(
            "index.html",
            inbox_count=inbox_count,
            recent_notes=recent_notes,
            active_projects=active_projects,
            pending_tasks=pending_tasks,
        )

    # ─── Error Handlers ─────────────────────────────────────────────────────

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "not found"}), 404
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Server error: {e}")
        if request.path.startswith("/api/"):
            return jsonify({"error": "internal server error"}), 500
        return render_template("500.html"), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
