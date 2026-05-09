"""Backfill migration for Project.area_id and Task.area_id/note_id.

This repo does not currently use Alembic. This script performs additive ALTER TABLE
operations safely for SQLite and can be run idempotently.
"""

from sqlalchemy import inspect, text

from app import create_app
from extensions import db


ADDITIVE_COLUMNS = {
    "projects": [
        "ALTER TABLE projects ADD COLUMN area_id VARCHAR(36) REFERENCES areas (id)",
    ],
    "tasks": [
        "ALTER TABLE tasks ADD COLUMN area_id VARCHAR(36) REFERENCES areas (id)",
        "ALTER TABLE tasks ADD COLUMN note_id VARCHAR(36) REFERENCES notes (id)",
    ],
}


def _missing_columns(table_name: str, desired: set[str]) -> set[str]:
    inspector = inspect(db.engine)
    existing = {col["name"] for col in inspector.get_columns(table_name)}
    return desired - existing


def upgrade():
    with db.engine.begin() as conn:
        for table_name, statements in ADDITIVE_COLUMNS.items():
            missing = _missing_columns(
                table_name,
                {stmt.split(" ADD COLUMN ", 1)[1].split()[0] for stmt in statements},
            )
            for statement in statements:
                column_name = statement.split(" ADD COLUMN ", 1)[1].split()[0]
                if column_name in missing:
                    conn.execute(text(statement))


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        upgrade()
        print("Migration complete.")
