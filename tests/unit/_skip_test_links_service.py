"""Unit tests for services/links.py."""
import pytest
from extensions import db
from models import Link


class TestCreateEmbeddingLinks:
    def test_creates_links(self, app):
        from services.links import create_embedding_links

        with app.app_context():
            related = [("note-2", 0.95), ("note-3", 0.88)]
            create_embedding_links("note-1", related)

            links = Link.query.filter(Link.src_id == "note-1").all()
            assert len(links) == 2
            assert links[0].link_type == "related"
            assert links[0].source == "embedding"

    def test_skips_self_links(self, app):
        from services.links import create_embedding_links

        with app.app_context():
            related = [("note-1", 0.99)]
            create_embedding_links("note-1", related)

            links = Link.query.filter(Link.src_id == "note-1").all()
            assert len(links) == 0

    def test_skips_duplicates(self, app):
        from services.links import create_embedding_links

        with app.app_context():
            related = [("note-2", 0.95)]
            create_embedding_links("note-1", related)
            create_embedding_links("note-1", related)

            links = Link.query.filter(Link.src_id == "note-1").all()
            assert len(links) == 1

    def test_skips_reverse_duplicates(self, app):
        from services.links import create_embedding_links

        with app.app_context():
            create_embedding_links("note-2", [("note-1", 0.95)])
            create_embedding_links("note-1", [("note-2", 0.95)])

            links = Link.query.filter(
                ((Link.src_id == "note-1") & (Link.dst_id == "note-2")) |
                ((Link.src_id == "note-2") & (Link.dst_id == "note-1"))
            ).all()
            assert len(links) == 1

    def test_empty_related(self, app):
        from services.links import create_embedding_links

        with app.app_context():
            create_embedding_links("note-1", [])
            links = Link.query.filter(Link.src_id == "note-1").all()
            assert len(links) == 0

    def test_rounds_weight(self, app):
        from services.links import create_embedding_links

        with app.app_context():
            related = [("note-2", 0.954321)]
            create_embedding_links("note-1", related)

            link = Link.query.filter(Link.src_id == "note-1").first()
            assert link.weight == 0.9543
