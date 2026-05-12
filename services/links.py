"""Link/graph helper functions used by ingestion and API — DEPRECATED.

This module used the v1 Link model. The v2 replacement uses EntityLink
via services/link_service.py create_link().
"""
import logging

logger = logging.getLogger(__name__)

VALID_LINK_TYPES = {"related", "child_of", "depends_on", "see_also", "mentions"}


def create_embedding_links(src_note_id: str, related: list[tuple[str, float]]):
    """DEPRECATED: Use link_service.create_link() instead."""
    logger.warning(
        "create_embedding_links is deprecated — use link_service.create_link() instead"
    )
