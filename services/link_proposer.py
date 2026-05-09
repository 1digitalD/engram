"""
Propose undirected note-to-note links for human review.

Combines:
- Semantic similarity: sqlite-vec + OpenAI embeddings when available; lexical Jaccard fallback.
- Shared entities: area, tags (Jaccard), projects (M2M + primary), linked person.
- Temporal patterns: notes created close in time get a confidence boost.

Returns dicts: from_note_id, to_note_id, reason, confidence (0–1).
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


class LinkProposal(TypedDict):
    from_note_id: str
    to_note_id: str
    reason: str
    confidence: float


def _token_set(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _STOPWORDS and len(w) > 1}


def lexical_similarity(text_a: str, text_b: str) -> float:
    """Rough 0–1 overlap score for notes without embedding hits."""
    sa, sb = _token_set(text_a), _token_set(text_b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def _note_pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def _canonical_direction(created_a: datetime, id_a: str, created_b: datetime, id_b: str) -> tuple[str, str]:
    """Older note is 'from', newer is 'to' when timestamps differ."""
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


def _vector_related_note_ids(
    nid: str,
    *,
    limit: int,
    min_similarity: float,
) -> list[tuple[str, float]]:
    """Wrap sqlite-vec search; disabled under Flask TESTING to avoid vec segfaults on :memory: DBs."""
    try:
        from flask import current_app

        if current_app.config.get("TESTING"):
            return []
    except RuntimeError:
        pass
    try:
        from services.embeddings import find_related_note_ids

        return find_related_note_ids(nid, limit=limit, min_similarity=min_similarity)
    except Exception as e:
        logger.debug(f"semantic candidates skipped for {nid}: {e}")
        return []


def _collect_candidate_pairs(
    pool: set[str],
    notes_by_id: dict,
    semantic_min: float,
    semantic_k: int,
) -> dict[tuple[str, str], float]:
    """Map undirected pair -> best semantic score seen (0 if unknown)."""
    best_sem: dict[tuple[str, str], float] = defaultdict(float)
    for nid in pool:
        if nid not in notes_by_id:
            continue
        related = _vector_related_note_ids(nid, limit=semantic_k, min_similarity=semantic_min)
        for other_id, sim in related:
            if other_id not in pool or other_id == nid:
                continue
            key = _note_pair_key(nid, other_id)
            if sim > best_sem[key]:
                best_sem[key] = sim

    na = len(pool)
    if na <= 80:
        ids = sorted(pool)
        for i, a in enumerate(ids):
            n_a = notes_by_id.get(a)
            if not n_a:
                continue
            for b in ids[i + 1 :]:
                n_b = notes_by_id.get(b)
                if not n_b:
                    continue
                key = _note_pair_key(a, b)
                lex = lexical_similarity(n_a.raw_text or "", n_b.raw_text or "")
                if lex >= 0.08 and lex > best_sem[key]:
                    best_sem[key] = min(1.0, lex * 1.15)

    by_area: dict[str | None, list[str]] = defaultdict(list)
    by_person: dict[str | None, list[str]] = defaultdict(list)
    by_tag: dict[str, list[str]] = defaultdict(list)
    by_project: dict[str, list[str]] = defaultdict(list)

    for nid in pool:
        n = notes_by_id.get(nid)
        if not n:
            continue
        if n.area_id:
            by_area[n.area_id].append(nid)
        if n.person_id:
            by_person[n.person_id].append(nid)
        for t in n.tags or []:
            by_tag[t.id].append(nid)
        pids = {p.id for p in (n.projects or [])}
        if n.project_id:
            pids.add(n.project_id)
        for pid in pids:
            by_project[pid].append(nid)

    def add_entity_pairs(ids_in_group: list[str]):
        u = sorted(set(ids_in_group) & pool)
        if len(u) < 2:
            return
        for i, a in enumerate(u):
            for b in u[i + 1 :]:
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
) -> list[LinkProposal]:
    """
    Build link proposals for review (does not persist links).

    :param note_ids: Notes to consider (sources and targets). If None, all non-archived notes up to max_notes.
    """
    from sqlalchemy.orm import joinedload

    from extensions import db
    from models import Link, Note

    if note_ids is None:
        q = (
            Note.query.filter_by(is_archived=False)
            .order_by(Note.modified_at.desc())
            .limit(max_notes)
        )
        pool = {n.id for n in q.all()}
    else:
        pool = {str(x) for x in note_ids}

    if len(pool) < 2:
        return []

    notes = (
        Note.query.options(
            joinedload(Note.tags),
            joinedload(Note.projects),
        )
        .filter(Note.id.in_(pool), Note.is_archived.is_(False))
        .all()
    )
    notes_by_id: dict[str, Note] = {n.id: n for n in notes}
    pool = {i for i in pool if i in notes_by_id}

    if len(pool) < 2:
        return []

    linked_pairs: set[tuple[str, str]] = set()
    for row in db.session.query(Link.src_id, Link.dst_id).all():
        linked_pairs.add(_note_pair_key(row[0], row[1]))

    pair_best_sem = _collect_candidate_pairs(pool, notes_by_id, semantic_min_similarity, semantic_neighbors)

    out: list[LinkProposal] = []
    for (ida, idb), sem_score in pair_best_sem.items():
        if ida == idb:
            continue
        key = (ida, idb)
        if key in linked_pairs:
            continue
        na, nb = notes_by_id[ida], notes_by_id[idb]
        tags_a = {t.id for t in (na.tags or [])}
        tags_b = {t.id for t in (nb.tags or [])}
        proj_a = {p.id for p in (na.projects or [])}
        proj_b = {p.id for p in (nb.projects or [])}
        if na.project_id:
            proj_a.add(na.project_id)
        if nb.project_id:
            proj_b.add(nb.project_id)
        proj_a.discard(None)
        proj_b.discard(None)

        ent_score, ent_parts = _entity_signal(
            na.area_id, nb.area_id, tags_a, tags_b, proj_a, proj_b, na.person_id, nb.person_id
        )
        if sem_score <= 0 and ent_score < 0.18:
            continue

        if sem_score <= 0 and ent_score >= 0.18:
            sem_display = lexical_similarity(na.raw_text or "", nb.raw_text or "")
        else:
            sem_display = sem_score

        temp_f, temp_note = _temporal_factor(na.created_at, nb.created_at, temporal_window_days)

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
        fid, tid = _canonical_direction(na.created_at, na.id, nb.created_at, nb.id)

        out.append(
            LinkProposal(
                from_note_id=fid,
                to_note_id=tid,
                reason=reason,
                confidence=round(confidence, 4),
            )
        )

    out.sort(key=lambda p: (-p["confidence"], p["from_note_id"], p["to_note_id"]))
    return out[:max_proposals]
