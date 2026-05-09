"""Create resources table and resource_tags association.

Idempotent on SQLite — skips work if ``resources`` already exists.
This repo uses manual migrations (no Alembic). Run::

    PYTHONPATH=. python migrations/006_resource_model.py
"""

from sqlalchemy import inspect, text

from app import create_app
from extensions import db

DDL_RESOURCES = """
CREATE TABLE resources (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    created_at DATETIME,
    modified_at DATETIME,
    title VARCHAR(500) NOT NULL,
    resource_type VARCHAR(20) NOT NULL,
    url VARCHAR(2048),
    author VARCHAR(255),
    published_at DATETIME,
    description TEXT,
    my_notes TEXT,
    is_read BOOLEAN DEFAULT 0,
    rating INTEGER,
    area_id VARCHAR(36) REFERENCES areas(id)
)
"""

DDL_RESOURCE_TAGS = """
CREATE TABLE resource_tags (
    resource_id VARCHAR(36) NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    tag_id VARCHAR(36) NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (resource_id, tag_id)
)
"""


def upgrade():
    insp = inspect(db.engine)
    if "resources" not in insp.get_table_names():
        with db.engine.begin() as conn:
            conn.execute(text(DDL_RESOURCES))
    insp = inspect(db.engine)
    if "resource_tags" not in insp.get_table_names():
        with db.engine.begin() as conn:
            conn.execute(text(DDL_RESOURCE_TAGS))


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        upgrade()
        print("Migration resources/resource_tags complete.")
