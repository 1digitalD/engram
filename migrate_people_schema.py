"""
One-time migration: people table schema check + fix.

Run from the engram root directory:
    python migrate_people_schema.py

What it does:
  1. Checks whether the `people` table has `external_ids` (new) or `discord_id` (old).
  2. If `external_ids` is missing, adds the column.
  3. If `discord_id` exists, migrates any non-null values into `external_ids`
     as {"discord": "<value>"} and then drops the old column (SQLite-safe rename-swap).
  4. If the schema is already correct, prints a confirmation and exits cleanly.

No data is deleted unless you had actual discord_id values — those are moved,
not lost. All notes, projects, areas, tasks, and tags are completely unaffected.
"""

import json
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "engram.db")

def column_names(cursor, table):
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def main():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        print("Run `flask init-db` to initialise a fresh database.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cols = column_names(cur, "people")
    print(f"Current people table columns: {sorted(cols)}")

    has_external_ids = "external_ids" in cols
    has_discord_id   = "discord_id"   in cols

    if has_external_ids and not has_discord_id:
        print("✓ Schema is correct — no migration needed.")
        conn.close()
        return

    if has_external_ids and has_discord_id:
        print("Both columns exist — migrating discord_id values into external_ids, then dropping discord_id.")
        cur.execute("SELECT id, discord_id, external_ids FROM people WHERE discord_id IS NOT NULL")
        rows = cur.fetchall()
        for person_id, discord_id, ext_raw in rows:
            try:
                ext = json.loads(ext_raw) if ext_raw else {}
            except (json.JSONDecodeError, TypeError):
                ext = {}
            ext["discord"] = discord_id
            cur.execute(
                "UPDATE people SET external_ids = ? WHERE id = ?",
                (json.dumps(ext), person_id)
            )
        print(f"  Migrated {len(rows)} discord_id value(s).")
        # SQLite can't DROP COLUMN on older versions — do a table rebuild
        _rebuild_without_discord_id(cur, conn)
        conn.commit()
        print("✓ Migration complete — discord_id removed, external_ids populated.")

    elif not has_external_ids and has_discord_id:
        print("Old schema detected — adding external_ids and migrating discord_id values.")
        cur.execute("ALTER TABLE people ADD COLUMN external_ids TEXT")
        cur.execute("SELECT id, discord_id FROM people WHERE discord_id IS NOT NULL")
        rows = cur.fetchall()
        for person_id, discord_id in rows:
            cur.execute(
                "UPDATE people SET external_ids = ? WHERE id = ?",
                (json.dumps({"discord": discord_id}), person_id)
            )
        print(f"  Migrated {len(rows)} discord_id value(s).")
        _rebuild_without_discord_id(cur, conn)
        conn.commit()
        print("✓ Migration complete.")

    elif not has_external_ids and not has_discord_id:
        print("Adding missing external_ids column (no discord_id to migrate).")
        cur.execute("ALTER TABLE people ADD COLUMN external_ids TEXT")
        conn.commit()
        print("✓ external_ids column added.")

    conn.close()


def _rebuild_without_discord_id(cur, conn):
    """Rebuild the people table without the discord_id column (SQLite-safe)."""
    cur.execute("PRAGMA table_info(people)")
    all_cols = cur.fetchall()
    keep = [c for c in all_cols if c[1] != "discord_id"]
    col_defs   = ", ".join(f'"{c[1]}" {c[2]}' + (' NOT NULL' if c[3] else '') + (f' DEFAULT {c[4]}' if c[4] is not None else '') for c in keep)
    col_names  = ", ".join(f'"{c[1]}"' for c in keep)

    cur.execute("PRAGMA foreign_keys=OFF")
    cur.execute(f"CREATE TABLE people_new ({col_defs})")
    cur.execute(f"INSERT INTO people_new ({col_names}) SELECT {col_names} FROM people")
    cur.execute("DROP TABLE people")
    cur.execute("ALTER TABLE people_new RENAME TO people")
    cur.execute("PRAGMA foreign_keys=ON")


if __name__ == "__main__":
    main()
