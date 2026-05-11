"""Rename ``weekly_summaries`` to ``summaries`` and add layered summary columns.

Idempotent on SQLite. If ``summaries`` already exists, missing columns are added.
If only ``weekly_summaries`` exists, it is renamed then upgraded. If neither
exists, ``summaries`` is created with the new schema.

Run::

    PYTHONPATH=. python migrations/007_summary_model.py
"""

from sqlalchemy import inspect, text

from app import create_app
from extensions import db

DDL_SUMMARIES_NEW = """
CREATE TABLE summaries (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    created_at DATETIME,
    modified_at DATETIME,
    note_id VARCHAR(36) NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    summary_text TEXT NOT NULL,
    generated_at DATETIME NOT NULL,
    summary_type VARCHAR(64),
    granularity VARCHAR(20) NOT NULL DEFAULT 'WEEKLY',
    date_from DATETIME,
    date_to DATETIME,
    key_themes JSON,
    action_items JSON,
    area_id VARCHAR(36) REFERENCES areas(id)
)
"""


def _column_names(table: str) -> set:
    with db.engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def _add_columns_for_summaries(table: str) -> None:
    """Add any columns required by the Summary model that are missing."""
    cols = _column_names(table)
    alters = []
    if "note_id" not in cols:
        alters.append(
            "note_id VARCHAR(36) REFERENCES notes(id) ON DELETE CASCADE"
        )
    if "summary_text" not in cols:
        alters.append("summary_text TEXT")
    if "generated_at" not in cols:
        alters.append("generated_at DATETIME")
    if "summary_type" not in cols:
        alters.append("summary_type VARCHAR(64)")
    if "granularity" not in cols:
        alters.append("granularity VARCHAR(20) DEFAULT 'WEEKLY'")
    if "date_from" not in cols:
        alters.append("date_from DATETIME")
    if "date_to" not in cols:
        alters.append("date_to DATETIME")
    if "key_themes" not in cols:
        alters.append("key_themes JSON")
    if "action_items" not in cols:
        alters.append("action_items JSON")
    if "area_id" not in cols:
        alters.append("area_id VARCHAR(36) REFERENCES areas(id)")

    if not alters:
        return

    with db.engine.begin() as conn:
        for clause in alters:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {clause}"))

    # Backfill from legacy weekly_summaries-shaped columns when present
    cols_after = _column_names(table)
    with db.engine.begin() as conn:
        if "summary_text" in cols_after and "summary_content" in cols_after:
            conn.execute(
                text(
                    f"""
                    UPDATE {table}
                    SET summary_text = summary_content
                    WHERE summary_text IS NULL AND summary_content IS NOT NULL
                    """
                )
            )
        if "generated_at" in cols_after:
            conn.execute(
                text(
                    f"""
                    UPDATE {table}
                    SET generated_at = created_at
                    WHERE generated_at IS NULL AND created_at IS NOT NULL
                    """
                )
            )
        if "granularity" in cols_after:
            conn.execute(
                text(
                    f"""
                    UPDATE {table} SET granularity = 'WEEKLY'
                    WHERE granularity IS NULL
                    """
                )
            )
        # Rows that cannot satisfy the new FK/note requirement are dropped
        if "note_id" in cols_after:
            conn.execute(text(f"DELETE FROM {table} WHERE note_id IS NULL"))
        if "summary_text" in cols_after:
            conn.execute(
                text(
                    f"""
                    DELETE FROM {table}
                    WHERE summary_text IS NULL OR TRIM(summary_text) = ''
                    """
                )
            )


def upgrade():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    if "summaries" in tables:
        _add_columns_for_summaries("summaries")
        return

    if "weekly_summaries" in tables:
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE weekly_summaries RENAME TO summaries"))
        _add_columns_for_summaries("summaries")
        return

    with db.engine.begin() as conn:
        conn.execute(text(DDL_SUMMARIES_NEW))


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        upgrade()
        print("Migration summaries complete.")
