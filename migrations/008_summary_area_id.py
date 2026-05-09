"""Add optional ``area_id`` to ``summaries`` for area-scoped rollups.

Run::

    PYTHONPATH=. python migrations/008_summary_area_id.py
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
    if "area_id" in cols:
        return
    with db.engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE summaries ADD COLUMN "
                "area_id VARCHAR(36) REFERENCES areas(id)"
            )
        )


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        upgrade()
        print("Migration summaries.area_id complete.")
