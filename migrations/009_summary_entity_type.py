"""Add ``entity_type`` to ``summaries`` for system health snapshots and similar.

Run::

    PYTHONPATH=. python migrations/009_summary_entity_type.py
"""

from sqlalchemy import inspect, text

from app import create_app
from extensions import db


def upgrade():
    inspector = inspect(db.engine)
    if "summaries" not in inspector.get_table_names():
        return
    with db.engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(summaries)")).fetchall()
    cols = {r[1] for r in rows}
    if "entity_type" in cols:
        return
    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE summaries ADD COLUMN entity_type VARCHAR(32)"))


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        upgrade()
        print("Migration summaries.entity_type complete.")
