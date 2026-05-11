"""Create note_projects M2M table and backfill from notes.project_id.

Idempotent on SQLite — skips work if ``note_projects`` already exists.
This repo uses manual migrations (no Alembic). Run::

    PYTHONPATH=. python migrations/005_note_projects_m2m.py
"""

from sqlalchemy import inspect, text

from app import create_app
from extensions import db


DDL = """
CREATE TABLE note_projects (
    note_id VARCHAR(36) NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    PRIMARY KEY (note_id, project_id)
)
"""

BACKFILL = """
INSERT OR IGNORE INTO note_projects (note_id, project_id)
SELECT id, project_id FROM notes WHERE project_id IS NOT NULL
"""


def upgrade():
    inspector = inspect(db.engine)
    if "note_projects" in inspector.get_table_names():
        return
    with db.engine.begin() as conn:
        conn.execute(text(DDL))
        conn.execute(text(BACKFILL))


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        upgrade()
        print("Migration note_projects complete.")
