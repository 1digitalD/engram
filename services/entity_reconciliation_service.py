"""Entity Reconciliation Service — matches detected entities to existing ones.

Responsibilities:
- Find existing entity candidates
- Score match confidence using type-specific matching signals
- Return best match or ambiguous matches
- Prevent duplicates
"""

import logging
import re
from difflib import SequenceMatcher

from extensions import db
from models import Entity, EntityLink

logger = logging.getLogger(__name__)

# Thresholds
EXACT_MATCH_CONFIDENCE = 0.97
FUZZY_MATCH_CONFIDENCE = 0.88
SIMILARITY_THRESHOLD = 0.70


def reconcile_person(name, email=None):
    """Find existing person by name or email.

    Args:
        name: Person name to match.
        email: Optional email for exact match.

    Returns:
        dict with matched_entity, confidence, match_type or None.
    """
    if not name:
        return None

    name_lower = name.strip().lower()

    # Exact title match
    exact = Entity.query.filter(
        Entity.type == "person",
        Entity.title.ilike(name_lower),
        Entity.lifecycle != "archived",
    ).first()
    if exact:
        return {
            "matched_entity": exact,
            "confidence": EXACT_MATCH_CONFIDENCE,
            "match_type": "exact_title",
        }

    # Email match from properties
    if email:
        email_entities = Entity.query.filter(
            Entity.type == "person",
            Entity.properties["email"].astext.ilike(email.strip().lower()),
            Entity.lifecycle != "archived",
        ).all()
        if email_entities:
            return {
                "matched_entity": email_entities[0],
                "confidence": EXACT_MATCH_CONFIDENCE,
                "match_type": "email",
            }

    # Fuzzy title match
    candidates = Entity.query.filter(
        Entity.type == "person",
        Entity.lifecycle != "archived",
    ).all()

    best = None
    best_score = 0
    for c in candidates:
        if not c.title:
            continue
        score = SequenceMatcher(None, name_lower, c.title.lower()).ratio()
        if score > best_score:
            best_score = score
            best = c

    if best and best_score >= FUZZY_MATCH_CONFIDENCE:
        return {
            "matched_entity": best,
            "confidence": round(best_score, 4),
            "match_type": "fuzzy_title",
        }

    if best and best_score >= SIMILARITY_THRESHOLD:
        return {
            "matched_entity": best,
            "confidence": round(best_score, 4),
            "match_type": "weak_fuzzy",
            "ambiguous": True,
        }

    return None


def reconcile_resource(url=None, title=None):
    """Find existing resource by URL or title.

    Args:
        url: Resource URL for exact match.
        title: Resource title for fuzzy match.

    Returns:
        dict with matched_entity, confidence, match_type or None.
    """
    # URL exact match
    if url:
        url_clean = url.strip().lower()
        url_match = Entity.query.filter(
            Entity.type == "resource",
            Entity.reference_url.ilike(url_clean),
        ).first()
        if url_match:
            return {
                "matched_entity": url_match,
                "confidence": EXACT_MATCH_CONFIDENCE,
                "match_type": "exact_url",
            }

    # Title match
    if title:
        title_lower = title.strip().lower()
        exact = Entity.query.filter(
            Entity.type == "resource",
            Entity.title.ilike(title_lower),
        ).first()
        if exact:
            return {
                "matched_entity": exact,
                "confidence": EXACT_MATCH_CONFIDENCE,
                "match_type": "exact_title",
            }

        # Fuzzy
        candidates = Entity.query.filter(
            Entity.type == "resource",
            Entity.lifecycle != "archived",
        ).all()

        best = None
        best_score = 0
        for c in candidates:
            if not c.title:
                continue
            score = SequenceMatcher(None, title_lower, c.title.lower()).ratio()
            if score > best_score:
                best_score = score
                best = c

        if best and best_score >= FUZZY_MATCH_CONFIDENCE:
            return {
                "matched_entity": best,
                "confidence": round(best_score, 4),
                "match_type": "fuzzy_title",
            }

    return None


def reconcile_project(title, area_id=None):
    """Find existing project by title, semantic similarity, or linked area.

    Args:
        title: Project name.
        area_id: Optional area ID for context matching.

    Returns:
        dict with matched_entity, confidence, match_type or None.
    """
    if not title:
        return None

    title_lower = title.strip().lower()

    # Exact title match (active projects)
    exact = Entity.query.filter(
        Entity.type == "project",
        Entity.title.ilike(title_lower),
        Entity.lifecycle == "active",
    ).first()
    if exact:
        return {
            "matched_entity": exact,
            "confidence": EXACT_MATCH_CONFIDENCE,
            "match_type": "exact_title_active",
        }

    # Exact title match (any lifecycle)
    exact_any = Entity.query.filter(
        Entity.type == "project",
        Entity.title.ilike(title_lower),
    ).first()
    if exact_any:
        return {
            "matched_entity": exact_any,
            "confidence": 0.94,
            "match_type": "exact_title",
        }

    # Fuzzy title match
    candidates = Entity.query.filter(
        Entity.type == "project",
        Entity.lifecycle != "archived",
    ).all()

    best = None
    best_score = 0
    for c in candidates:
        if not c.title:
            continue
        # Boost score if area matches
        area_boost = 0.05 if area_id and getattr(c, 'area_id', None) == area_id else 0
        score = SequenceMatcher(None, title_lower, c.title.lower()).ratio() + area_boost
        if score > best_score:
            best_score = score
            best = c

    if best and best_score >= FUZZY_MATCH_CONFIDENCE:
        return {
            "matched_entity": best,
            "confidence": round(min(best_score, 0.99), 4),
            "match_type": "fuzzy_title",
        }

    if best and best_score >= SIMILARITY_THRESHOLD:
        return {
            "matched_entity": best,
            "confidence": round(best_score, 4),
            "match_type": "weak_fuzzy",
            "ambiguous": True,
        }

    return None


def reconcile_area(title):
    """Find existing area by title.

    Args:
        title: Area name.

    Returns:
        dict with matched_entity, confidence, match_type or None.
    """
    if not title:
        return None

    title_lower = title.strip().lower()

    exact = Entity.query.filter(
        Entity.type == "area",
        Entity.title.ilike(title_lower),
        Entity.lifecycle == "active",
    ).first()
    if exact:
        return {
            "matched_entity": exact,
            "confidence": EXACT_MATCH_CONFIDENCE,
            "match_type": "exact_title_active",
        }

    # Fuzzy
    candidates = Entity.query.filter(
        Entity.type == "area",
        Entity.lifecycle != "archived",
    ).all()

    best = None
    best_score = 0
    for c in candidates:
        if not c.title:
            continue
        score = SequenceMatcher(None, title_lower, c.title.lower()).ratio()
        if score > best_score:
            best_score = score
            best = c

    if best and best_score >= FUZZY_MATCH_CONFIDENCE:
        return {
            "matched_entity": best,
            "confidence": round(best_score, 4),
            "match_type": "fuzzy_title",
        }

    return None


def reconcile_task(title, project_id=None, person_id=None):
    """Find existing task by title, status, linked project/person.

    Args:
        title: Task description.
        project_id: Optional project ID filter.
        person_id: Optional person ID filter.

    Returns:
        dict with matched_entity, confidence, match_type or None.
    """
    if not title:
        return None

    title_lower = title.strip().lower()

    # Exact title match on pending tasks
    exact = Entity.query.filter(
        Entity.type == "task",
        Entity.title.ilike(title_lower),
        Entity.status.in_(["pending", "in_progress"]),
    ).first()
    if exact:
        result = {
            "matched_entity": exact,
            "confidence": 0.95,
            "match_type": "exact_title_pending",
        }
        if person_id:
            result["person_id"] = person_id
        return result

    # Fuzzy match
    candidates = Entity.query.filter(
        Entity.type == "task",
        Entity.status.in_(["pending", "in_progress"]),
    ).all()

    best = None
    best_score = 0
    for c in candidates:
        if not c.title:
            continue
        score = SequenceMatcher(None, title_lower, c.title.lower()).ratio()
        if project_id:
            c_project_id = c.properties.get("project_id") if c.properties else None
            if c_project_id == project_id:
                score += 0.05
        if score > best_score:
            best_score = score
            best = c

    if best and best_score >= FUZZY_MATCH_CONFIDENCE:
        result = {
            "matched_entity": best,
            "confidence": round(min(best_score, 0.99), 4),
            "match_type": "fuzzy_title",
        }
        if person_id:
            result["person_id"] = person_id
        return result

    return None


def reconcile_all(detected_entities):
    """Run reconciliation for a list of detected entities.

    Args:
        detected_entities: List of dicts with type, name, and optional
                          url, email, project_id, person_id, area_id.

    Returns:
        List of reconciliation results.
    """
    results = []
    for de in detected_entities:
        etype = de.get("type")
        name = de.get("name")
        result = None

        if etype == "person":
            result = reconcile_person(name, email=de.get("email"))
        elif etype == "resource":
            result = reconcile_resource(url=de.get("url"), title=name)
        elif etype == "project":
            result = reconcile_project(name, area_id=de.get("area_id"))
        elif etype == "area":
            result = reconcile_area(name)
        elif etype == "task":
            result = reconcile_task(
                name,
                project_id=de.get("project_id"),
                person_id=de.get("person_id"),
            )
        elif etype == "note":
            # Notes are never auto-merged
            result = None

        results.append({
            "detected": de,
            "reconciliation": result,
        })

    return results
