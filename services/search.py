"""
Hybrid search: Postgres FTS (tsvector) + pgvector semantic search, fused with RRF.
Mode: hybrid | fts | semantic
"""
import logging
from extensions import db
from models import Entity

logger = logging.getLogger(__name__)

RRF_K = 60  # standard RRF constant


def search(query, limit=20, mode="hybrid", filters=None):
    """
    Universal entity search. mode: 'hybrid' | 'fts' | 'semantic'
    filters: dict with optional type, status, lifecycle keys.
    """
    if not query or not query.strip():
        return []

    if filters is None:
        filters = {}

    if mode == "semantic":
        results = _semantic_only(query, limit * 3, filters)
    elif mode == "fts":
        results = _fts_only(query, limit * 3, filters)
    else:
        results = _hybrid(query, limit, filters)

    return results


def _fts_only(query, limit, filters=None):
    """Full-text search using Postgres tsvector column."""
    filters = filters or {}
    try:
        sql = """
            SELECT id FROM entities
            WHERE search_vector @@ plainto_tsquery('english', :query)
              AND lifecycle = 'active'
            ORDER BY ts_rank(search_vector, plainto_tsquery('english', :query)) DESC
            LIMIT :limit
        """
        params = {"query": query, "limit": limit}

        if filters.get("type"):
            sql = sql.replace("LIMIT", "AND type = :etype LIMIT")
            params["etype"] = filters["type"]

        rows = db.session.execute(db.text(sql), params).fetchall()
        entity_ids = [row[0] for row in rows]
        if not entity_ids:
            return []

        entities = Entity.query.filter(Entity.id.in_(entity_ids)).all()
        entities_map = {e.id: e for e in entities}
        return [entities_map[eid].to_dict() for eid in entity_ids if eid in entities_map]
    except Exception as e:
        logger.error("FTS search error: %s", e)
        return []


def _semantic_only(query, limit, filters=None):
    """Semantic search via pgvector cosine similarity on entity_chunks."""
    from services.embeddings import embed_query

    vector = embed_query(query)
    if vector is None:
        return []

    try:
        embedding_str = "[{}]".format(",".join(str(v) for v in vector))

        where_clause = "ec.embedding IS NOT NULL AND ec.entity_id IN (SELECT id FROM entities WHERE lifecycle = 'active')"
        params = {"embedding": embedding_str, "limit": limit}

        if filters.get("type"):
            where_clause += " AND ec.entity_id IN (SELECT id FROM entities WHERE type = :etype)"
            params["etype"] = filters["type"]

        sql = """
            SELECT ec.entity_id,
                   MAX(1 - (ec.embedding <-> :embedding)::float) AS similarity
            FROM entity_chunks ec
            WHERE {}
            GROUP BY ec.entity_id
            ORDER BY similarity DESC
            LIMIT :limit
        """.format(where_clause)

        rows = db.session.execute(db.text(sql), params).fetchall()
        entity_ids = [row[0] for row in rows]
        if not entity_ids:
            return []

        entities = Entity.query.filter(Entity.id.in_(entity_ids)).all()
        entities_map = {e.id: e for e in entities}
        results = []
        for row in rows:
            if row[0] in entities_map:
                d = entities_map[row[0]].to_dict()
                d["_score"] = round(row[1], 4)
                results.append(d)
        return results
    except Exception as e:
        logger.error("Semantic search error: %s", e)
        return []


def _hybrid(query, limit, filters=None):
    """Hybrid RRF fusion of FTS and semantic search."""
    fts_results = _fts_only(query, limit * 3, filters)
    semantic_results = _semantic_only(query, limit * 3, filters)
    return _rrf_fusion(fts_results, semantic_results, limit)


def _rrf_fusion(fts_results, semantic_results, limit):
    """
    Reciprocal Rank Fusion: score(d) = sum(1 / (k + rank_i)) across systems.
    """
    fts_ranks = {r["id"]: i + 1 for i, r in enumerate(fts_results)}
    sem_ranks = {r["id"]: i + 1 for i, r in enumerate(semantic_results)}

    all_ids = set(fts_ranks) | set(sem_ranks)
    if not all_ids:
        return []

    scores = {}
    for eid in all_ids:
        rrf = 0.0
        if eid in fts_ranks:
            rrf += 1.0 / (RRF_K + fts_ranks[eid])
        if eid in sem_ranks:
            rrf += 1.0 / (RRF_K + sem_ranks[eid])
        scores[eid] = rrf

    note_cache = {}
    for r in fts_results + semantic_results:
        note_cache[r["id"]] = r

    ranked = sorted(scores.items(), key=lambda x: -x[1])[:limit]

    results = []
    for eid, score in ranked:
        if eid in note_cache:
            d = note_cache[eid].copy()
        else:
            obj = db.session.get(Entity, eid)
            if not obj:
                continue
            d = obj.to_dict()
        d["_score"] = round(score, 6)
        d["_fts_rank"] = fts_ranks.get(eid)
        d["_sem_rank"] = sem_ranks.get(eid)
        results.append(d)

    return results


def find_related(entity_id, limit=5, min_similarity=0.80):
    """
    Find entities semantically similar to the given entity via pgvector.
    Returns list of (entity_id, similarity_score) tuples.
    """
    from models import EntityChunk
    from sqlalchemy import text

    chunks = EntityChunk.query.filter_by(entity_id=entity_id).all()
    if not chunks:
        return []

    primary_chunk = chunks[0]
    if not primary_chunk.embedding:
        return []

    try:
        embedding_str = "[{}]".format(",".join(str(v) for v in primary_chunk.embedding))

        rows = db.session.execute(text("""
            SELECT ec.entity_id,
                   MAX(1 - (ec.embedding <-> :embedding)::float) AS similarity
            FROM entity_chunks ec
            WHERE ec.entity_id != :exclude_id
              AND ec.embedding IS NOT NULL
            GROUP BY ec.entity_id
            ORDER BY similarity DESC
            LIMIT :limit
        """), {
            "embedding": embedding_str,
            "exclude_id": entity_id,
            "limit": limit * 3,
        }).fetchall()

        return [
            (row[0], round(row[1], 4))
            for row in rows
            if row[1] >= min_similarity
        ][:limit]
    except Exception as e:
        logger.debug("find_related failed: %s", e)
        return []


# ── Backward-compat aliases (Cycle 1 — superseded by search() above) ─────────

def search_notes(query, limit=20, mode="hybrid", bucket=None, project_id=None, area_id=None):
    """Legacy wrapper for backward compatibility with existing API imports."""
    filters = {}
    if bucket:
        filters["type"] = "note"
    return search(query, limit=limit, mode=mode, filters=filters)
