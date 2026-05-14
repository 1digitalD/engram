"""
Propose undirected entity-to-entity links for human review.

Combines:
- Semantic similarity: pgvector + OpenAI embeddings when available; lexical Jaccard fallback.
- Shared entities: area, tags (Jaccard), projects (EntityLink M2M).
- Temporal patterns: entities created close in time get a confidence boost.

Returns dicts: from_note_id, to_note_id, reason, confidence (0–1).

Uses Entity, EntityLink, EntityTag. Bulk-loads tags and project/area links.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import TypedDict

logger = logging.getLogger(__name__)

_STOPWORDS = frozenset(
    "a an the to of and or for in on at is are was were be been being it this that these those "
    "with as by from than then not no yes but if so we you our their i me my they them he she "
    "have has had do did does can could would should will just into out up more most some any "
    "all each both about over also only very when what which who how why".split()
)


class ProposedLink(TypedDict):
    from_note_id: str
    to_note_id: str
    reason: str
    confidence: float


def _token_set(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _STOPWORDS and len(w) > 1}


def lexical_similarity(text_a: str, text_b: str) -> float:
    """Rough 0–1 overlap score for entities without embedding hits."""
    sa, sb = _token_set(text_a), _token_set(text_b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def _note_pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def _canonical_direction(created_a: datetime, id_a: str, created_b: datetime, id_b: str) -> tuple[str, str]:
    """Older entity is 'from', newer is 'to' when timestamps differ."""
    if created_a == created_b:
        return (id_a, id_b) if id_a < id_b else (id_b, id_a)
    if created_a < created_b:
        return id_a, id_b
    return id_b, id_a


def _entity_signal(
    area_a, area_b, tags_a: set[str], tags_b: set[str], proj_a: set[str], proj_b: set[str], person_a, person_b
) -> tuple[float, list[str]]:
    parts: list[str] = []
    score = 0.0
    if area_a and area_b and area_a == area_b:
        score += 0.42
        parts.append("same area")
    if tags_a and tags_b:
        inter = tags_a & tags_b
        if inter:
            j = len(inter) / len(tags_a | tags_b)
            score += 0.38 * j
            parts.append(f"{len(inter)} shared tag(s)")
    if proj_a and proj_b and (proj_a & proj_b):
        score += 0.28
        parts.append("shared project")
    if person_a and person_b and person_a == person_b:
        score += 0.22
        parts.append("same linked person")
    return min(1.0, score), parts


def _temporal_factor(created_a: datetime, created_b: datetime, window_days: int) -> tuple[float, str | None]:
    delta = abs((created_a - created_b).total_seconds()) / 86400.0
    if delta <= window_days:
        return 1.0, f"created within {max(1, int(delta))} day(s)"
    # soften long gaps
    excess = delta - window_days
    return max(0.12, 1.0 - excess / 90.0), None


def _vector_related_entity_ids(
    eid: str,
    *,
    limit: int,
    min_similarity: float,
) -> list[tuple[str, float]]:
    """Wrap pgvector search; disabled under Flask TESTING."""
    try:
        from flask import current_app

        if current_app.config.get("TESTING"):
            return []
    except RuntimeError:
        pass
    try:
        from services.embeddings import find_related_note_ids

        return find_related_note_ids(eid, limit=limit, min_similarity=min_similarity)
    except Exception as e:
        logger.debug(f"semantic candidates skipped for {eid}: {e}")
        return []


class _EntityContext:
    """Bulk-loaded context for a set of entities to avoid N+1 queries."""

    def __init__(self, entity_ids: set[str], entity_type_cache: dict[str, str] | None = None):
        self.tag_ids_by_entity: dict[str, set[str]] = defaultdict(set)
        self.area_ids_by_entity: dict[str, str | None] = {}
        self.project_ids_by_entity: dict[str, set[str]] = defaultdict(set)
        self.person_ids_by_entity: dict[str, str | None] = {}
        type_cache = entity_type_cache or {}

        if not entity_ids:
            return

        from models import Entity, EntityLink, EntityTag

        # Bulk-load tags
        rows = (
            EntityTag.query
            .filter(EntityTag.entity_id.in_(entity_ids))
            .all()
        )
        for row in rows:
            self.tag_ids_by_entity[str(row.entity_id)].add(str(row.tag_id))

        # Bulk-load area/project/person links
        link_rows = (
            EntityLink.query
            .filter(
                EntityLink.src_id.in_(entity_ids),
                EntityLink.link_type.in_(["related", "parent"]),
            )
            .all()
        )

        # Collect all dst_ids that we need types for
        needed_dst_ids = {link.dst_id for link in link_rows} - set(type_cache.keys())
        if needed_dst_ids:
            type_rows = Entity.query.with_entities(Entity.id, Entity.type).filter(Entity.id.in_(needed_dst_ids)).all()
            for row in type_rows:
                type_cache[str(row.id)] = row.type

        for link in link_rows:
            dst_type = type_cache.get(str(link.dst_id))
            if dst_type == "area":
                self.area_ids_by_entity[str(link.src_id)] = str(link.dst_id)
            elif dst_type == "project":
                self.project_ids_by_entity[str(link.src_id)].add(str(link.dst_id))
            elif dst_type == "person":
                self.person_ids_by_entity[str(link.src_id)] = str(link.dst_id)


def _build_entity_type_cache(entity_ids: set[str]) -> dict[str, str]:
    """Bulk-load entity types to avoid per-entity queries."""
    from models import Entity

    if not entity_ids:
        return {}
    rows = Entity.query.with_entities(Entity.id, Entity.type).filter(Entity.id.in_(entity_ids)).all()
    return {str(row.id): row.type for row in rows}


def _collect_candidate_pairs(
    pool: set[str],
    entities_by_id: dict,
    ctx: _EntityContext,
    semantic_min: float,
    semantic_k: int,
) -> dict[tuple[str, str], float]:
    """Map undirected pair -> best semantic score seen (0 if unknown)."""
    best_sem: dict[tuple[str, str], float] = defaultdict(float)
    for eid in pool:
        if eid not in entities_by_id:
            continue
        related = _vector_related_entity_ids(eid, limit=semantic_k, min_similarity=semantic_min)
        for other_id, sim in related:
            if other_id not in pool or other_id == eid:
                continue
            key = _note_pair_key(eid, other_id)
            if sim > best_sem[key]:
                best_sem[key] = sim

    na = len(pool)
    if na <= 80:
        ids = sorted(pool)
        for i, a in enumerate(ids):
            e_a = entities_by_id.get(a)
            if not e_a:
                continue
            for b in ids[i + 1:]:
                e_b = entities_by_id.get(b)
                if not e_b:
                    continue
                key = _note_pair_key(a, b)
                lex = lexical_similarity(e_a.content or "", e_b.content or "")
                if lex >= 0.08 and lex > best_sem[key]:
                    best_sem[key] = min(1.0, lex * 1.15)

    # Group by shared entity context (bulk-loaded, no N+1)
    by_area: dict[str | None, list[str]] = defaultdict(list)
    by_person: dict[str | None, list[str]] = defaultdict(list)
    by_tag: dict[str, list[str]] = defaultdict(list)
    by_project: dict[str, list[str]] = defaultdict(list)

    for eid in pool:
        if eid in ctx.area_ids_by_entity:
            aid = ctx.area_ids_by_entity[eid]
            if aid:
                by_area[aid].append(eid)
        if eid in ctx.person_ids_by_entity:
            pid = ctx.person_ids_by_entity[eid]
            if pid:
                by_person[pid].append(eid)
        for tid in ctx.tag_ids_by_entity.get(eid, set()):
            by_tag[tid].append(eid)
        for pid in ctx.project_ids_by_entity.get(eid, set()):
            by_project[pid].append(eid)

    def add_entity_pairs(ids_in_group: list[str]):
        u = sorted(set(ids_in_group) & pool)
        if len(u) < 2:
            return
        for i, a in enumerate(u):
            for b in u[i + 1:]:
                key = _note_pair_key(a, b)
                best_sem.setdefault(key, 0.0)

    for g in by_area.values():
        add_entity_pairs(g)
    for g in by_person.values():
        add_entity_pairs(g)
    for g in by_tag.values():
        add_entity_pairs(g)
    for g in by_project.values():
        add_entity_pairs(g)

    return dict(best_sem)


def propose_links(
    note_ids: Sequence[str] | None = None,
    *,
    max_notes: int = 500,
    min_confidence: float = 0.38,
    temporal_window_days: int = 14,
    semantic_min_similarity: float = 0.72,
    semantic_neighbors: int = 14,
    max_proposals: int = 400,
) -> list[ProposedLink]:
    """
    Build link proposals for review (does not persist links).

    :param note_ids: Entity IDs to consider (sources and targets).
        If None, all non-archived note entities up to max_notes.
    """
    from extensions import db
    from models import Entity, EntityLink

    if note_ids is None:
        q = (
            Entity.query.with_entities(Entity.id)
            .filter_by(type="note", lifecycle="active")
            .order_by(Entity.updated_at.desc())
            .limit(max_notes)
        )
        pool = {row.id for row in q.all()}
    else:
        pool = {str(x) for x in note_ids}

    if len(pool) < 2:
        return []

    # Bulk-load entity types
    entity_type_cache = _build_entity_type_cache(pool)

    entities = (
        Entity.query
        .filter(Entity.id.in_(pool), Entity.type == "note", Entity.lifecycle != "archived")
        .all()
    )
    entities_by_id: dict[str, Entity] = {str(e.id): e for e in entities}
    pool = {i for i in pool if i in entities_by_id}

    if len(pool) < 2:
        return []

    # Bulk-load context (tags, area/project/person links) — no N+1
    ctx = _EntityContext(pool, entity_type_cache)

    # Bulk-load existing links
    linked_pairs: set[tuple[str, str]] = set()
    for row in db.session.query(EntityLink.src_id, EntityLink.dst_id).all():
        linked_pairs.add(_note_pair_key(str(row[0]), str(row[1])))

    pair_best_sem = _collect_candidate_pairs(pool, entities_by_id, ctx, semantic_min_similarity, semantic_neighbors)

    out: list[ProposedLink] = []
    for (ida, idb), sem_score in pair_best_sem.items():
        if ida == idb:
            continue
        key = (ida, idb)
        if key in linked_pairs:
            continue
        ea, eb = entities_by_id[ida], entities_by_id[idb]
        tags_a = ctx.tag_ids_by_entity.get(ida, set())
        tags_b = ctx.tag_ids_by_entity.get(idb, set())
        proj_a = ctx.project_ids_by_entity.get(ida, set())
        proj_b = ctx.project_ids_by_entity.get(idb, set())
        area_a = ctx.area_ids_by_entity.get(ida)
        area_b = ctx.area_ids_by_entity.get(idb)
        person_a = ctx.person_ids_by_entity.get(ida)
        person_b = ctx.person_ids_by_entity.get(idb)

        ent_score, ent_parts = _entity_signal(
            area_a, area_b, tags_a, tags_b, proj_a, proj_b, person_a, person_b
        )
        if sem_score <= 0 and ent_score < 0.18:
            continue

        if sem_score <= 0 and ent_score >= 0.18:
            sem_display = lexical_similarity(ea.content or "", eb.content or "")
        else:
            sem_display = sem_score

        temp_f, temp_note = _temporal_factor(ea.created_at, eb.created_at, temporal_window_days)

        confidence = min(
            1.0,
            0.48 * min(1.0, sem_display) + 0.37 * ent_score + 0.15 * temp_f,
        )
        if confidence < min_confidence:
            continue

        reason_parts: list[str] = []
        if sem_score > 0:
            reason_parts.append(f"semantic similarity ~{round(sem_display, 2)}")
        elif sem_display >= 0.1:
            reason_parts.append(f"lexical overlap ~{round(sem_display, 2)}")
        if ent_parts:
            reason_parts.append("shared context: " + ", ".join(ent_parts))
        if temp_note:
            reason_parts.append(temp_note)

        reason = "; ".join(reason_parts) if reason_parts else "related notes"
        fid, tid = _canonical_direction(ea.created_at, str(ea.id), eb.created_at, str(eb.id))

        out.append(
            ProposedLink(
                from_note_id=fid,
                to_note_id=tid,
                reason=reason,
                confidence=round(confidence, 4),
            )
        )

    out.sort(key=lambda p: (-p["confidence"], p["from_note_id"], p["to_note_id"]))
    return out[:max_proposals]
