#!/usr/bin/env python3
"""Export replay fixtures from production for reconciliation eval.

Reads the production DB (READ-ONLY) and writes JSON fixtures to
tests/fixtures/replay/:

  catalog.json      — active projects + areas (id/type/title/content_preview)
  suggestions.json  — dismissed + accepted suggestions with source note content
  README.md         — instructions for labeling

Labels are written manually to tests/fixtures/replay/labels.json after export.
The replay_eval.py script reads labels.json to score pipeline decisions.

Usage:
    python scripts/export_replay_fixtures.py

Env:
    DATABASE_URL — defaults to postgresql://engram:engram@localhost:5432/engram
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "tests" / "fixtures" / "replay"
DB_URL = os.environ.get("DATABASE_URL", "postgresql://engram:engram@localhost:5432/engram")

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("psycopg2 not found. Run: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[export] Connecting to {DB_URL}")
    conn = psycopg2.connect(DB_URL)
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Entity catalog: active projects and areas (used by reconciler matching)
    cur.execute("""
        SELECT
            id,
            type,
            title,
            left(content, 400) AS content_preview,
            status,
            created_at::text,
            updated_at::text
        FROM entities
        WHERE type IN ('project', 'area')
          AND lifecycle = 'active'
        ORDER BY updated_at DESC
    """)
    catalog = [dict(r) for r in cur.fetchall()]
    (OUT_DIR / "catalog.json").write_text(json.dumps(catalog, indent=2, default=str))
    print(f"[export] catalog.json: {len(catalog)} entities")

    # Also include active persons and tasks for broader replay context
    cur.execute("""
        SELECT id, type, title, status, left(content, 200) AS content_preview
        FROM entities
        WHERE type IN ('person', 'task', 'resource')
          AND lifecycle = 'active'
        ORDER BY updated_at DESC
        LIMIT 200
    """)
    broader = [dict(r) for r in cur.fetchall()]
    (OUT_DIR / "catalog_broad.json").write_text(json.dumps(broader, indent=2, default=str))
    print(f"[export] catalog_broad.json: {len(broader)} entities")

    # Suggestions: dismissed and accepted, with their source note content
    cur.execute("""
        SELECT
            s.id,
            s.suggestion_type,
            s.status,
            s.payload,
            s.created_at::text,
            e.id AS source_note_id,
            e.content AS source_note_content,
            e.title AS source_note_title,
            e.ai_meta
        FROM ai_suggestions s
        LEFT JOIN entities e ON e.id = s.source_entity_id
        WHERE s.status IN ('dismissed', 'accepted')
        ORDER BY s.created_at DESC
    """)
    suggestions = []
    for r in cur.fetchall():
        row = dict(r)
        # payload may be a dict already (psycopg2 with json column)
        if isinstance(row.get("payload"), str):
            try:
                row["payload"] = json.loads(row["payload"])
            except Exception:
                pass
        if isinstance(row.get("ai_meta"), str):
            try:
                row["ai_meta"] = json.loads(row["ai_meta"])
            except Exception:
                pass
        suggestions.append(row)

    (OUT_DIR / "suggestions.json").write_text(json.dumps(suggestions, indent=2, default=str))
    print(f"[export] suggestions.json: {len(suggestions)} suggestions")

    # Recent notes for broader replay (last 30 days of captures)
    cur.execute("""
        SELECT id, title, content, ai_meta, source, created_at::text
        FROM entities
        WHERE type = 'note'
          AND lifecycle = 'active'
          AND source IN ('ai_capture', 'quick_capture', 'manual')
        ORDER BY created_at DESC
        LIMIT 50
    """)
    notes = []
    for r in cur.fetchall():
        row = dict(r)
        if isinstance(row.get("ai_meta"), str):
            try:
                row["ai_meta"] = json.loads(row["ai_meta"])
            except Exception:
                pass
        notes.append(row)

    (OUT_DIR / "notes.json").write_text(json.dumps(notes, indent=2, default=str))
    print(f"[export] notes.json: {len(notes)} notes")

    conn.close()

    # Write labels template if it doesn't exist yet (preserve hand-edits)
    labels_path = OUT_DIR / "labels.json"
    if not labels_path.exists():
        labels = []
        for s in suggestions:
            suggested_title = (s.get("payload") or {}).get("title", "")
            labels.append({
                "suggestion_id": s["id"],
                "suggestion_type": s["suggestion_type"],
                "status": s["status"],
                "suggested_title": suggested_title,
                "source_note_title": s.get("source_note_title", ""),
                # Fill in manually:
                # "new"    — genuinely new entity, create was correct
                # "update" — should have matched+updated an existing entity
                # "link"   — should have linked to an existing entity (no field change)
                # "accept" — accepted suggestion, action was correct
                "expected_action": "TODO",
                "expected_target_title": "",  # if update/link: title of the existing entity
                "notes": "",
            })
        labels_path.write_text(json.dumps(labels, indent=2))
        print(f"[export] labels.json: {len(labels)} entries — FILL IN expected_action MANUALLY")
    else:
        print(f"[export] labels.json already exists — skipping overwrite (hand-edits preserved)")

    readme = """# Replay Fixtures

Generated by `scripts/export_replay_fixtures.py` from production data.

## Files

- `catalog.json`       — active projects + areas at export time
- `catalog_broad.json` — active tasks, persons, resources
- `notes.json`         — recent capture notes
- `suggestions.json`   — all dismissed + accepted AI suggestions with source note content
- `labels.json`        — hand-labeled expected decisions (FILL THIS IN)

## Labeling `labels.json`

For each entry in `labels.json`, set `expected_action` to one of:

- `"new"`    — the suggestion was correct; a new entity should be created
- `"update"` — the suggestion should have matched and updated an existing entity;
               set `expected_target_title` to the existing entity's title
- `"link"`   — should have linked to existing (no field update needed);
               set `expected_target_title`
- `"accept"` — for accepted suggestions; the action was correct

Set `notes` to explain your reasoning for any non-obvious label.

## Running the eval

    python scripts/replay_eval.py

Reads `labels.json`, runs the live pipeline (extraction + reconciliation)
against each source note's content + the frozen catalog, and prints a score.
Results are written to `docs/iterations/replay_results/<timestamp>.json`.
"""
    (OUT_DIR / "README.md").write_text(readme)
    print(f"[export] Done. Fixtures written to {OUT_DIR}/")
    print(f"[export] Next step: edit tests/fixtures/replay/labels.json")
    print(f"[export]   Set expected_action for each suggestion before running replay_eval.py")


if __name__ == "__main__":
    main()
