"""Link/graph helper functions used by ingestion and API."""
import logging

logger = logging.getLogger(__name__)

VALID_LINK_TYPES = {"related", "child_of", "depends_on", "see_also", "mentions"}


def create_embedding_links(src_note_id: str, related: list[tuple[str, float]]):
    """
    Create 'related' links between src_note_id and related note ids.
    related: list of (note_id, similarity_score) tuples.
    Skips if link already exists.
    """
    from extensions import db
    from models import Link

    created = 0
    for dst_note_id, similarity in related:
        if dst_note_id == src_note_id:
            continue
        # Check both directions
        exists = Link.query.filter(
            ((Link.src_id == src_note_id) & (Link.dst_id == dst_note_id)) |
            ((Link.src_id == dst_note_id) & (Link.dst_id == src_note_id))
        ).first()
        if exists:
            continue
        link = Link(
            src_id=src_note_id,
            dst_id=dst_note_id,
            link_type="related",
            weight=round(similarity, 4),
            source="embedding",
        )
        db.session.add(link)
        created += 1

    if created:
        try:
            db.session.commit()
            logger.debug(f"Auto-linked {created} notes to {src_note_id}")
        except Exception as e:
            db.session.rollback()
            logger.warning(f"Auto-link commit failed: {e}")
