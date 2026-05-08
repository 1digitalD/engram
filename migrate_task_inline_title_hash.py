"""Add Task.inline_title_hash for markdown checkbox inline task extraction.

Idempotent ALTER TABLE for SQLite. Run once on existing databases; new installs
get the column via db.create_all() from models.
"""

from sqlalchemy import inspect, text

from app import create_app
from extensions import db


def upgrade():
    inspector = inspect(db.engine)
    existing = {col["name"] for col in inspector.get_columns("tasks")}
    if "inline_title_hash" in existing:
        return
    with db.engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE tasks ADD COLUMN inline_title_hash VARCHAR(64)")
        )


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        upgrade()
        print("Migration complete.")
