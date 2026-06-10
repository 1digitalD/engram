#!/usr/bin/env python3
"""Slice D1 one-time assist: list active projects and their current priority.

Tasks inherit their parent project's `properties.priority` when they have no
priority of their own (see services/v4_attention.py). This script gives Dan a
quick read-out of which active projects still have no priority set, so he can
bulk-edit them via the Projects list UI (each project's priority is editable
the same way as a task's).

Read-only: makes no changes.

Usage:
  python scripts/list_project_priorities.py [--missing-only]

Database connection from DATABASE_URL env var, default:
  postgresql://engram:engram@localhost:5432/engram
"""

import argparse
import os

import psycopg2
import psycopg2.extras

DEFAULT_DB_URL = "postgresql://engram:engram@localhost:5432/engram"


def list_project_priorities(db_url, missing_only=False):
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, title, properties->>'priority' AS priority, updated_at
                FROM entities
                WHERE type = 'project' AND lifecycle = 'active' AND status = 'active'
                ORDER BY updated_at DESC
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if missing_only:
        rows = [r for r in rows if not r["priority"]]

    if not rows:
        print("No active projects" + (" without a priority" if missing_only else "") + ".")
        return

    for row in rows:
        priority = row["priority"] or "(none)"
        print(f"{row['id']}  {priority:8s}  {row['title']}")

    missing = sum(1 for r in rows if not r["priority"])
    print(f"\n{len(rows)} active project(s), {missing} without a priority set.")


def main():
    parser = argparse.ArgumentParser(description="List active projects and their priority")
    parser.add_argument("--missing-only", action="store_true",
                        help="Only list projects with no priority set")
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL", DEFAULT_DB_URL)
    list_project_priorities(db_url, missing_only=args.missing_only)


if __name__ == "__main__":
    main()
