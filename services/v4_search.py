"""V4 search service with keyword, semantic, and hybrid RRF modes."""

import logging

from sqlalchemy import or_, text as sql_text

from extensions import db
from models import Entity, EntityChunk, EntityTag, Tag

logger = logging.getLogger(__name__)

TITLE_BOOST = 4.0
KEYWORD_CANDIDATE_MULTIPLIER = 25
KEYWORD_MAX_CANDIDATES = 500
SEMANTIC_SCORE_FLOOR = 0.1


def search_entities(query, mode="hybrid", entity_type=None, status=None, lifecycle="active", limit=20, tag=None):
    mode = mode if mode in {"keyword", "semantic", "hybrid"} else "hybrid"
    limit = max(1, min(int(limit or 20), 100))
    filters = dict(entity_type=entity_type, status=status, lifecycle=lifecycle, tag=tag)

    keyword_ranked = _keyword_search(query, filters, limit) if mode in {"keyword", "hybrid"} else []
    semantic_ranked = _semantic_search(query, filters, limit) if mode in {"semantic", "hybrid"} else []

    if mode == "keyword":
        return _format_results(keyword_ranked, keyword_ranked, [], limit)
    if mode == "semantic":
        return _format_results(semantic_ranked, [], semantic_ranked, limit)
    return _format_results(_rrf(keyword_ranked, semantic_ranked), keyword_ranked, semantic_ranked, limit)


def list_by_tag(tag_name, entity_type=None, status=None, lifecycle="active", limit=50):
    """Return entities with the given tag, no text query. Sorted by recency."""
    limit = max(1, min(int(limit or 50), 200))
    name = (tag_name or "").strip().lower()
    if not name:
        return []

    query = (
        Entity.query
        .join(EntityTag, EntityTag.entity_id == Entity.id)
        .join(Tag, Tag.id == EntityTag.tag_id)
        .filter(Tag.name == name)
    )
    if entity_type:
        query = query.filter(Entity.type == entity_type)
    if status:
        query = query.filter(Entity.status == status)
    if lifecycle:
        query = query.filter(Entity.lifecycle == lifecycle)

    entities = query.order_by(Entity.updated_at.desc()).limit(limit).all()
    return [
        {
            "entity": e.to_dict(),
            "score": 1.0,
            "match": {"source": "tag", "tag": name},
        }
        for e in entities
    ]


def _base_query(filters):
    query = Entity.query
    if filters.get("entity_type"):
        query = query.filter(Entity.type == filters["entity_type"])
    if filters.get("status"):
        query = query.filter(Entity.status == filters["status"])
    if filters.get("lifecycle"):
        query = query.filter(Entity.lifecycle == filters["lifecycle"])
    if filters.get("tag"):
        tag_name = filters["tag"].strip().lower()
        if tag_name:
            query = (
                query
                .join(EntityTag, EntityTag.entity_id == Entity.id)
                .join(Tag, Tag.id == EntityTag.tag_id)
                .filter(Tag.name == tag_name)
            )
    return query


def _keyword_search(search_query, filters, limit):
    terms = [term.lower() for term in search_query.split() if term.strip()]
    if not terms:
        return []

    query = _base_query(filters)
    term_filters = [
        or_(
            Entity.title.ilike(f"%{term}%"),
            Entity.content.ilike(f"%{term}%"),
        )
        for term in terms
    ]
    candidate_limit = min(max(limit * KEYWORD_CANDIDATE_MULTIPLIER, 100), KEYWORD_MAX_CANDIDATES)
    query = query.filter(or_(*term_filters)).order_by(Entity.updated_at.desc()).limit(candidate_limit)

    scored = []
    normalized_query = " ".join(terms)
    for entity in query.all():
        title_raw = entity.title or ""
        content_raw = entity.content or ""
        title_text = title_raw.lower()
        content_text = content_raw.lower()
        matched_terms = [term for term in terms if term in title_text or term in content_text]
        if not matched_terms:
            continue
        coverage_score = (len(set(matched_terms)) / len(set(terms))) * 10.0
        title_phrase_score = 8.0 if normalized_query and normalized_query in title_text else 0.0
        content_phrase_score = 3.0 if normalized_query and normalized_query in content_text else 0.0
        title_prefix_score = 2.0 if normalized_query and title_text.startswith(normalized_query) else 0.0
        title_score = sum(title_text.count(t) for t in terms) * TITLE_BOOST
        content_score = sum(content_text.count(t) for t in terms)
        score = coverage_score + title_phrase_score + content_phrase_score + title_prefix_score + title_score + content_score
        if score > 0:
            snippet_term = normalized_query if normalized_query in content_text else matched_terms[0]
            scored.append((entity, score, _snippet(content_raw or title_raw, snippet_term)))

    scored.sort(key=lambda row: (
        -row[1],
        -((row[0].updated_at or row[0].created_at).timestamp() if (row[0].updated_at or row[0].created_at) else 0),
        -(row[0].created_at.timestamp() if row[0].created_at else 0),
    ))
    return scored[:limit]


def _semantic_search(search_query, filters, limit):
    from services.embeddings import embed_query

    query_vector = embed_query(search_query)
    if not query_vector:
        return []

    vec_str = "[" + ",".join(str(v) for v in query_vector) + "]"
    prelimit = limit * 5

    conds = []
    params = {"qvec": vec_str, "prelimit": prelimit}
    extra_joins = ""
    conds.append("ec.embedding IS NOT NULL")
    if filters.get("lifecycle"):
        conds.append("e.lifecycle = :lifecycle")
        params["lifecycle"] = filters["lifecycle"]
    if filters.get("entity_type"):
        conds.append("e.type = :entity_type")
        params["entity_type"] = filters["entity_type"]
    if filters.get("status"):
        conds.append("e.status = :status")
        params["status"] = filters["status"]
    if filters.get("tag"):
        tag_name = filters["tag"].strip().lower()
        if tag_name:
            extra_joins += " JOIN entity_tags et ON et.entity_id = e.id JOIN tags t ON t.id = et.tag_id"
            conds.append("t.name = :tag_name")
            params["tag_name"] = tag_name

    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    sql = sql_text(f"""
        SELECT ec.entity_id, ec.chunk_text, 1 - (ec.embedding <=> CAST(:qvec AS vector)) AS score
        FROM entity_chunks ec
        JOIN entities e ON e.id = ec.entity_id{extra_joins}
        {where}
        ORDER BY ec.embedding <=> CAST(:qvec AS vector)
        LIMIT :prelimit
    """)

    try:
        rows = db.session.execute(sql, params).fetchall()
    except Exception as e:
        logger.error("semantic search SQL failed: %s", e)
        db.session.rollback()
        return []

    best = {}
    for entity_id, chunk_text, score in rows:
        if score is None or float(score) < SEMANTIC_SCORE_FLOOR:
            continue
        if entity_id not in best or score > best[entity_id][1]:
            best[entity_id] = (entity_id, float(score), chunk_text)

    if not best:
        return []

    ranked_ids = sorted(best, key=lambda eid: best[eid][1], reverse=True)[:limit]
    entities_by_id = {e.id: e for e in Entity.query.filter(Entity.id.in_(ranked_ids)).all()}

    return [
        (entities_by_id[eid], best[eid][1], _entity_snippet(entities_by_id[eid], best[eid][2]))
        for eid in ranked_ids
        if eid in entities_by_id
    ]


def _rrf(keyword_ranked, semantic_ranked, k=60):
    scores = {}
    payloads = {}
    for ranked in (keyword_ranked, semantic_ranked):
        for index, row in enumerate(ranked, start=1):
            entity = row[0]
            scores[entity.id] = scores.get(entity.id, 0.0) + 1.0 / (k + index)
            payloads[entity.id] = (entity, scores[entity.id], row[2])
    return sorted(payloads.values(), key=lambda row: row[1], reverse=True)


def _format_results(ranked, keyword_ranked, semantic_ranked, limit):
    keyword_ranks = {row[0].id: index for index, row in enumerate(keyword_ranked, start=1)}
    semantic_ranks = {row[0].id: index for index, row in enumerate(semantic_ranked, start=1)}
    semantic_scores = {row[0].id: row[1] for row in semantic_ranked}
    results = []
    for index, (entity, score, snippet) in enumerate(ranked[:limit], start=1):
        keyword_rank = keyword_ranks.get(entity.id)
        semantic_rank = semantic_ranks.get(entity.id)
        source = _match_source(keyword_rank, semantic_rank)
        match = {
            "source": source,
            "keyword_rank": keyword_rank,
            "semantic_rank": semantic_rank,
            "snippet": snippet,
        }
        if source in ("semantic", "hybrid") and entity.id in semantic_scores:
            match["semantic_score"] = round(float(semantic_scores[entity.id]), 4)
        results.append({
            "entity": entity.to_dict(),
            "score": score,
            "match": match,
        })
    return results


def _snippet(text, term):
    lowered = text.lower()
    index = lowered.find(term.lower())
    if index < 0:
        return text[:160]
    start = max(0, index - 60)
    return text[start:start + 160]


def _entity_snippet(entity, chunk_text):
    chunk = (chunk_text or "").strip()
    if chunk:
        return chunk[:160]
    content = (entity.content or "").strip()
    if content:
        return content[:160]
    return (entity.title or "")[:160]


def _match_source(keyword_rank, semantic_rank):
    if keyword_rank and semantic_rank:
        return "hybrid"
    if semantic_rank:
        return "semantic"
    if keyword_rank:
        return "keyword"
    return "unknown"
