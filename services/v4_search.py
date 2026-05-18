"""V4 search service with keyword, semantic, and hybrid RRF modes."""

import math

from extensions import db
from models import Entity, EntityChunk
from services.canonical_document import generate_canonical_markdown


def search_entities(query, mode="hybrid", entity_type=None, status=None, lifecycle=None, limit=20):
    mode = mode if mode in {"keyword", "semantic", "hybrid"} else "hybrid"
    limit = max(1, min(int(limit or 20), 100))
    filters = dict(entity_type=entity_type, status=status, lifecycle=lifecycle)

    keyword_ranked = _keyword_search(query, filters, limit) if mode in {"keyword", "hybrid"} else []
    semantic_ranked = _semantic_search(query, filters, limit) if mode in {"semantic", "hybrid"} else []

    if mode == "keyword":
        return _format_results(keyword_ranked, keyword_ranked, [], limit)
    if mode == "semantic":
        return _format_results(semantic_ranked, [], semantic_ranked, limit)
    return _format_results(_rrf(keyword_ranked, semantic_ranked), keyword_ranked, semantic_ranked, limit)


def _base_query(filters):
    query = Entity.query
    if filters.get("entity_type"):
        query = query.filter(Entity.type == filters["entity_type"])
    if filters.get("status"):
        query = query.filter(Entity.status == filters["status"])
    if filters.get("lifecycle"):
        query = query.filter(Entity.lifecycle == filters["lifecycle"])
    return query


def _keyword_search(search_query, filters, limit):
    terms = [term.lower() for term in search_query.split() if term.strip()]
    if not terms:
        return []
    scored = []
    for entity in _base_query(filters).all():
        text = generate_canonical_markdown(entity).lower()
        score = sum(text.count(term) for term in terms)
        if score > 0:
            scored.append((entity, float(score), _snippet(text, terms[0])))
    scored.sort(key=lambda row: (-row[1], row[0].updated_at or row[0].created_at), reverse=False)
    return scored[:limit]


def _semantic_search(search_query, filters, limit):
    from services.embeddings import _embed_texts

    vectors = _embed_texts([search_query])
    query_vector = vectors[0] if vectors else None
    if not query_vector:
        return []

    entity_ids = {entity.id for entity in _base_query(filters).all()}
    best = {}
    chunks = EntityChunk.query.filter(EntityChunk.entity_id.in_(entity_ids)).all() if entity_ids else []
    for chunk in chunks:
        vector = chunk.embedding
        if not vector:
            continue
        score = _cosine(query_vector, vector)
        current = best.get(chunk.entity_id)
        if current is None or score > current[1]:
            best[chunk.entity_id] = (chunk.entity, score, chunk.chunk_text[:160])
    ranked = sorted(best.values(), key=lambda row: row[1], reverse=True)
    return ranked[:limit]


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
    results = []
    for index, (entity, score, snippet) in enumerate(ranked[:limit], start=1):
        results.append({
            "entity": entity.to_dict(),
            "score": score,
            "match": {
                "keyword_rank": keyword_ranks.get(entity.id),
                "semantic_rank": semantic_ranks.get(entity.id),
                "snippet": snippet,
            },
        })
    return results


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _snippet(text, term):
    index = text.find(term)
    if index < 0:
        return text[:160]
    start = max(0, index - 60)
    return text[start:start + 160]
