#!/usr/bin/env python3
"""Backfill: create parent links from orphaned tasks to their source note's projects.

Finds all active tasks that:
  1. Have a `derived_from` link to a note
  2. Have zero `parent` links to any project

For each such task, finds the source note's project links (related, mentions,
parent) and creates `parent` links from the task to those projects. Also touches
each affected project's updated_at.

Run with --dry-run to preview without writing.
Run with --task-id <id> to target a specific task.

Usage:
  python scripts/backfill_task_project_links.py [--dry-run] [--task-id <id>]

Database connection from DATABASE_URL env var, default:
  postgresql://engram:engram@localhost:5432/engram
"""

import argparse
import os
import sys
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

DEFAULT_DB_URL = "postgresql://engram:engram@localhost:5432/engram"


def connect(db_url):
    return psycopg2.connect(db_url)


def find_orphaned_tasks(conn, task_id=None):
    """Find active tasks with derived_from links but no parent links."""
    query = """
        SELECT
            t.id AS task_id,
            t.title AS task_title,
            t.status AS task_status,
            n.id AS note_id,
            n.title AS note_title
        FROM entities t
        JOIN entity_links derived
            ON derived.source_entity_id = t.id
            AND derived.relationship_type = 'derived_from'
        JOIN entities n
            ON n.id = derived.target_entity_id
            AND n.type = 'note'
        WHERE t.type = 'task'
          AND t.lifecycle = 'active'
          AND NOT EXISTS (
              SELECT 1 FROM entity_links pl
              WHERE pl.source_entity_id = t.id
                AND pl.relationship_type = 'parent'
          )
    """
    if task_id:
        query += " AND t.id = %(task_id)s"

    query += " ORDER BY t.created_at"

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, {"task_id": task_id} if task_id else {})
        return cur.fetchall()


def find_note_projects(conn, note_id):
    """Find active projects linked to a note."""
    query = """
        SELECT DISTINCT
            p.id AS project_id,
            p.title AS project_title,
            nl.relationship_type AS via_relationship
        FROM entity_links nl
        JOIN entities p
            ON p.id = nl.target_entity_id
            AND p.type = 'project'
            AND p.lifecycle = 'active'
        WHERE nl.source_entity_id = %(note_id)s
          AND nl.relationship_type IN ('related', 'mentions', 'parent')
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, {"note_id": note_id})
        return cur.fetchall()


def parent_link_exists(conn, task_id, project_id):
    """Check if parent link already exists."""
    query = """
        SELECT EXISTS (
            SELECT 1 FROM entity_links
            WHERE source_entity_id = %(task_id)s
              AND target_entity_id = %(project_id)s
              AND relationship_type = 'parent'
        ) AS exists
    """
    with conn.cursor() as cur:
        cur.execute(query, {"task_id": task_id, "project_id": project_id})
        return cur.fetchone()[0]


def create_parent_link(conn, task_id, project_id, note_id, dry_run=False):
    """Create a parent link from task to project."""
    if dry_run:
        return True

    query = """
        INSERT INTO entity_links (
            source_entity_id, target_entity_id, relationship_type,
            source, confidence, evidence
        ) VALUES (
            %(task_id)s, %(project_id)s, 'parent',
            'backfill', 0.95,
            %(evidence)s
        )
    """
    evidence = f"backfill: inherited from note {note_id}"
    with conn.cursor() as cur:
        cur.execute(query, {
            "task_id": task_id,
            "project_id": project_id,
            "evidence": evidence,
        })
    return True


def touch_project(conn, project_id, dry_run=False):
    """Update project's updated_at timestamp."""
    if dry_run:
        return

    query = """
        UPDATE entities SET updated_at = %(now)s
        WHERE id = %(project_id)s
    """
    with conn.cursor() as cur:
        cur.execute(query, {
            "now": datetime.now(timezone.utc),
            "project_id": project_id,
        })


def run_backfill(db_url, dry_run=False, task_id=None):
    conn = connect(db_url)
    conn.autocommit = False

    try:
        orphaned = find_orphaned_tasks(conn, task_id)
        if not orphaned:
            print("No orphaned tasks found.")
            return

        print(f"Found {len(orphaned)} orphaned task(s)\n")

        total_links = 0
        skipped_tasks = 0

        for task in orphaned:
            projects = find_note_projects(conn, task["note_id"])
            if not projects:
                print(
                    f"  SKIP  task \"{task['task_title']}\" "
                    f"({task['task_id'][:8]}…) — note has no project links"
                )
                skipped_tasks += 1
                continue

            for project in projects:
                if parent_link_exists(conn, task["task_id"], project["project_id"]):
                    print(
                        f"  SKIP  task \"{task['task_title']}\" "
                        f"→ project \"{project['project_title']}\" — link exists"
                    )
                    continue

                tag = "[DRY RUN] " if dry_run else ""
                print(
                    f"  {tag}LINK  task \"{task['task_title']}\" "
                    f"→ project \"{project['project_title']}\" "
                    f"(via {project['via_relationship']} on note {task['note_id'][:8]}…)"
                )
                create_parent_link(
                    conn, task["task_id"], project["project_id"],
                    task["note_id"], dry_run=dry_run,
                )
                touch_project(conn, project["project_id"], dry_run=dry_run)
                total_links += 1

        if dry_run:
            print(f"\n[DRY RUN] Would create {total_links} parent links, "
                  f"{skipped_tasks} tasks skipped (no project references)")
            conn.rollback()
        else:
            conn.commit()
            print(f"\nDone: {total_links} parent link(s) created, "
                  f"{skipped_tasks} task(s) skipped")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Backfill task->project parent links")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing")
    parser.add_argument("--task-id", type=str, default=None,
                        help="Target a specific task ID")
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL", DEFAULT_DB_URL)
    run_backfill(db_url, dry_run=args.dry_run, task_id=args.task_id)


if __name__ == "__main__":
    main()
