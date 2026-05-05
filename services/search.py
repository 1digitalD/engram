"""
Hybrid search: FTS5 (BM25) + semantic vector search, fused with RRF.
Mode: hybrid | fts | semantic
"""
import logging
from extensions import db
from models import Note

logger = logging.getLogger(__name__)

RRF_K = 60  # standard RRF constant


def search_notes(query: str, limit: int = 20, mode: str = "hybrid") -> list[dict]:
    """
    Search notes. mode: 'hybrid' | 'fts' | 'semantic'
    - fts: SQLite FTS5 BM25 only
    - semantic: embedding cosine similarity only
    - hybrid: RRF fusion of both (default)
    """
    if not query or not query.strip():
        return []

    if mode == "semantic":
        return _semantic_only(query, limit)
    elif mode == "fts":
        return _fts_only(query, limit)
    else:
        return _hybrid(query, limit)


def _fts_only(query: str, limit: int) -> list[dict]:
    """FTS5 BM25 search with LIKE fallback."""
    fts_query = query.replace('"', '""')
    try:
        sql = db.text("""
            SELECT notes.id
            FROM notes
            JOIN notes_fts ON notes.rowid = notes_fts.rowid
            WHERE notes_fts MATCH :query
              AND notes.is_archived = 0
            ORDER BY rank
            LIMIT :limit
        """)
        rows = db.session.execute(sql, {"query": f'"{fts_query}"', "limit": limit}).fetchall()
        results = []
        for (note_id,) in rows:
            note = db.session.get(Note, note_id)
            if note:
                results.append(note.to_dict())
        return results
    except Exception as e:
        logger.error(f"FTS search error: {e}")
        return _like_fallback(query, limit)


def _semantic_only(query: str, limit: int) -> list[dict]:
    """Pure semantic search via embeddings."""
    try:
        from services.embeddings import semantic_search
        return semantic_search(query, limit=limit)
    except Exception as e:
        logger.error(f"Semantic search error: {e}")
        return []


def _hybrid(query: str, limit: int) -> list[dict]:
    """
    Hybrid RRF: get top results from FTS5 and semantic, fuse by rank.
    score(d) = sum(1 / (k + rank_i)) across systems.
    """
    fts_results = _fts_only(query, limit * 3)
    semantic_results = _semantic_only(query, limit * 3)

    # Build rank maps: note_id → rank (1-based)
    fts_ranks = {r["id"]: i + 1 for i, r in enumerate(fts_results)}
    sem_ranks = {r["id"]: i + 1 for i, r in enumerate(semantic_results)}

    # Collect all unique note ids
    all_ids = set(fts_ranks) | set(sem_ranks)
    if not all_ids:
        return []

    # RRF score: higher is better
    scores = {}
    for note_id in all_ids:
        rrf = 0.0
        if note_id in fts_ranks:
            rrf += 1.0 / (RRF_K + fts_ranks[note_id])
        if note_id in sem_ranks:
            rrf += 1.0 / (RRF_K + sem_ranks[note_id])
        scores[note_id] = rrf

    # Build id→note dict from what we already fetched
    note_cache = {}
    for r in fts_results + semantic_results:
        note_cache[r["id"]] = r

    ranked = sorted(scores.items(), key=lambda x: -x[1])[:limit]

    results = []
    for note_id, score in ranked:
        if note_id in note_cache:
            note = note_cache[note_id].copy()
        else:
            obj = db.session.get(Note, note_id)
            if not obj:
                continue
            note = obj.to_dict()
        note["_score"] = round(score, 6)
        note["_fts_rank"] = fts_ranks.get(note_id)
        note["_sem_rank"] = sem_ranks.get(note_id)
        results.append(note)

    return results


def _like_fallback(query: str, limit: int) -> list[dict]:
    """Simple LIKE fallback when FTS is unavailable."""
    notes = (
        Note.query
        .filter(Note.raw_text.ilike(f"%{query}%"), Note.is_archived == False)
        .order_by(Note.modified_at.desc())
        .limit(limit)
        .all()
    )
    return [n.to_dict() for n in notes]
