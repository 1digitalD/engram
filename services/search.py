import logging
from extensions import db
from models import Note

logger = logging.getLogger(__name__)


def search_notes(query: str, limit: int = 20) -> list[dict]:
    """
    Full-text search on notes using SQLite FTS5.
    Returns list of matching Note dicts.
    """
    if not query or not query.strip():
        return []

    # Escape FTS5 special characters
    fts_query = query.replace('"', '""')

    try:
        sql = db.text("""
            SELECT notes.id, notes.raw_text, notes.bucket, notes.created_at
            FROM notes
            JOIN notes_fts ON notes.rowid = notes_fts.rowid
            WHERE notes_fts MATCH :query
            ORDER BY rank
            LIMIT :limit
        """)
        result = db.session.execute(sql, {"query": f'"{fts_query}"', "limit": limit})
        rows = result.fetchall()

        notes = []
        for row in rows:
            note = db.session.get(Note, row[0])
            if note:
                notes.append(note.to_dict())

        return notes

    except Exception as e:
        logger.error(f"Search error: {e}")
        # Fallback to LIKE search
        return fallback_search(query, limit)


def fallback_search(query: str, limit: int = 20) -> list[dict]:
    """Simple LIKE fallback when FTS is unavailable."""
    notes = (
        Note.query.filter(Note.raw_text.ilike(f"%{query}%"))
        .order_by(Note.modified_at.desc())
        .limit(limit)
        .all()
    )
    return [n.to_dict() for n in notes]
