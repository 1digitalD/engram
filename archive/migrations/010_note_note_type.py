"""Add ``note_type`` to ``notes`` (NOTE/MOC/DAILY/MEETING/DECISION).

Run::

    PYTHONPATH=. python migrations/010_note_note_type.py
"""

from sqlalchemy import inspect, text

from app import create_app
from extensions import db


def upgrade():
    inspector = inspect(db.engine)
    if "notes" not in inspector.get_table_names():
        return
    with db.engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(notes)")).fetchall()
    cols = {r[1] for r in rows}
    if "note_type" in cols:
        return
    with db.engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE notes ADD COLUMN note_type VARCHAR(16) "
                "NOT NULL DEFAULT 'NOTE'"
            )
        )


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        upgrade()
        print("Migration notes.note_type complete.")
