"""Integration tests for link_service — create, delete, query, cascade.

Uses the Flask app fixture with in-memory SQLite.
"""

import json
import pytest

from extensions import db
from models import Entity, EntityEvent, EntityLink
from services.entity_service import create_entity
from services.link_service import (
    create_link,
    delete_link,
    get_links,
    delete_preview,
)


# ─── create_link ─────────────────────────────────────────────────────────────


class TestCreateLink:
    def test_create_related_link(self, app):
        with app.app_context():
            src = create_entity(entity_type="note", title="Src", actor="user")
            dst = create_entity(entity_type="note", title="Dst", actor="user")
            link = create_link(src.id, dst.id, actor="user")
            assert link.src_id == src.id
            assert link.dst_id == dst.id
            assert link.link_type == "related"
            assert link.source == "manual"

    def test_create_parent_link(self, app):
        with app.app_context():
            src = create_entity(entity_type="task", title="Task", actor="user")
            dst = create_entity(entity_type="project", title="Project", actor="user")
            link = create_link(
                src.id, dst.id, link_type="parent", actor="user"
            )
            assert link.link_type == "parent"

    def test_create_link_with_confidence(self, app):
        with app.app_context():
            src = create_entity(entity_type="note", title="Src", actor="user")
            dst = create_entity(entity_type="note", title="Dst", actor="user")
            link = create_link(
                src.id, dst.id, link_type="related", source="ai",
                confidence=0.95, evidence="similar content", actor="agent:classify"
            )
            assert link.confidence == 0.95
            assert link.evidence == "similar content"
            assert link.source == "ai"

    def test_create_link_writes_events(self, app):
        with app.app_context():
            src = create_entity(entity_type="note", title="Src", actor="user")
            dst = create_entity(entity_type="note", title="Dst", actor="user")
            create_link(src.id, dst.id, actor="user")
            src_events = EntityEvent.query.filter_by(
                entity_id=src.id, event_type="link_added"
            ).all()
            dst_events = EntityEvent.query.filter_by(
                entity_id=dst.id, event_type="link_added"
            ).all()
            assert len(src_events) == 1
            assert len(dst_events) == 1

    def test_create_link_src_not_found(self, app):
        with app.app_context():
            dst = create_entity(entity_type="note", title="Dst", actor="user")
            with pytest.raises(ValueError, match="source entity.*not found"):
                create_link("nonexistent", dst.id, actor="user")

    def test_create_link_dst_not_found(self, app):
        with app.app_context():
            src = create_entity(entity_type="note", title="Src", actor="user")
            with pytest.raises(ValueError, match="destination entity.*not found"):
                create_link(src.id, "nonexistent", actor="user")

    def test_create_self_link_rejected(self, app):
        with app.app_context():
            entity = create_entity(entity_type="note", title="Self", actor="user")
            with pytest.raises(ValueError, match="cannot link entity to itself"):
                create_link(entity.id, entity.id, actor="user")

    def test_create_duplicate_link_rejected(self, app):
        with app.app_context():
            src = create_entity(entity_type="note", title="Src", actor="user")
            dst = create_entity(entity_type="note", title="Dst", actor="user")
            create_link(src.id, dst.id, actor="user")
            with pytest.raises(ValueError, match="link already exists"):
                create_link(src.id, dst.id, actor="user")

    def test_create_duplicate_different_type_allowed(self, app):
        with app.app_context():
            src = create_entity(entity_type="note", title="Src", actor="user")
            dst = create_entity(entity_type="note", title="Dst", actor="user")
            create_link(src.id, dst.id, link_type="related", actor="user")
            # Different link type should be allowed
            link2 = create_link(src.id, dst.id, link_type="references", actor="user")
            assert link2.link_type == "references"

    def test_parent_cardinality_enforced(self, app):
        with app.app_context():
            src = create_entity(entity_type="task", title="Task", actor="user")
            dst1 = create_entity(entity_type="project", title="P1", actor="user")
            dst2 = create_entity(entity_type="project", title="P2", actor="user")
            create_link(src.id, dst1.id, link_type="parent", actor="user")
            with pytest.raises(ValueError, match="already has a parent"):
                create_link(src.id, dst2.id, link_type="parent", actor="user")

    def test_different_link_types_for_parent_not_blocked(self, app):
        with app.app_context():
            src = create_entity(entity_type="note", title="Src", actor="user")
            dst1 = create_entity(entity_type="note", title="Dst1", actor="user")
            dst2 = create_entity(entity_type="note", title="Dst2", actor="user")
            create_link(src.id, dst1.id, link_type="related", actor="user")
            # Related link doesn't block parent link
            link2 = create_link(src.id, dst2.id, link_type="parent", actor="user")
            assert link2.link_type == "parent"


# ─── delete_link ─────────────────────────────────────────────────────────────


class TestDeleteLink:
    def test_delete_link(self, app):
        with app.app_context():
            src = create_entity(entity_type="note", title="Src", actor="user")
            dst = create_entity(entity_type="note", title="Dst", actor="user")
            link = create_link(src.id, dst.id, actor="user")
            delete_link(link.id, actor="user")
            assert EntityLink.query.get(link.id) is None

    def test_delete_link_writes_events(self, app):
        with app.app_context():
            src = create_entity(entity_type="note", title="Src", actor="user")
            dst = create_entity(entity_type="note", title="Dst", actor="user")
            link = create_link(src.id, dst.id, actor="user")
            delete_link(link.id, actor="user")
            src_events = EntityEvent.query.filter_by(
                entity_id=src.id, event_type="link_removed"
            ).all()
            dst_events = EntityEvent.query.filter_by(
                entity_id=dst.id, event_type="link_removed"
            ).all()
            assert len(src_events) == 1
            assert len(dst_events) == 1

    def test_delete_link_not_found(self, app):
        with app.app_context():
            with pytest.raises(ValueError, match="link.*not found"):
                delete_link("nonexistent", actor="user")


# ─── get_links ───────────────────────────────────────────────────────────────


class TestGetLinks:
    def test_get_outgoing_links(self, app):
        with app.app_context():
            src = create_entity(entity_type="note", title="Src", actor="user")
            dst1 = create_entity(entity_type="note", title="Dst1", actor="user")
            dst2 = create_entity(entity_type="note", title="Dst2", actor="user")
            create_link(src.id, dst1.id, actor="user")
            create_link(src.id, dst2.id, actor="user")
            links = get_links(src.id, direction="outgoing")
            assert len(links) == 2

    def test_get_incoming_links(self, app):
        with app.app_context():
            src = create_entity(entity_type="note", title="Src", actor="user")
            dst = create_entity(entity_type="note", title="Dst", actor="user")
            create_link(src.id, dst.id, actor="user")
            links = get_links(dst.id, direction="incoming")
            assert len(links) == 1
            assert links[0].src_id == src.id

    def test_get_both_directions(self, app):
        with app.app_context():
            a = create_entity(entity_type="note", title="A", actor="user")
            b = create_entity(entity_type="note", title="B", actor="user")
            create_link(a.id, b.id, actor="user")
            create_link(b.id, a.id, actor="user")
            links = get_links(a.id, direction="both")
            assert len(links) == 2

    def test_filter_by_link_types(self, app):
        with app.app_context():
            src = create_entity(entity_type="note", title="Src", actor="user")
            dst1 = create_entity(entity_type="note", title="Dst1", actor="user")
            dst2 = create_entity(entity_type="note", title="Dst2", actor="user")
            create_link(src.id, dst1.id, link_type="related", actor="user")
            create_link(src.id, dst2.id, link_type="parent", actor="user")
            links = get_links(src.id, direction="outgoing", link_types=["parent"])
            assert len(links) == 1
            assert links[0].link_type == "parent"

    def test_no_links_returns_empty(self, app):
        with app.app_context():
            entity = create_entity(entity_type="note", title="Lonely", actor="user")
            links = get_links(entity.id)
            assert links == []


# ─── delete_preview (link_service) ───────────────────────────────────────────


class TestLinkDeletePreview:
    def test_preview_no_links(self, app):
        with app.app_context():
            entity = create_entity(entity_type="note", title="Test", actor="user")
            preview = delete_preview(entity.id)
            assert preview["entity"]["id"] == entity.id
            assert preview["safe_to_cascade"] == []
            assert preview["blocked"] == []

    def test_preview_orphan_detected(self, app):
        with app.app_context():
            parent = create_entity(entity_type="note", title="Parent", actor="user")
            child = create_entity(entity_type="note", title="Child", actor="user")
            create_link(parent.id, child.id, link_type="related", actor="user")
            preview = delete_preview(parent.id)
            assert child.id in preview["safe_to_cascade"]

    def test_preview_blocked_detected(self, app):
        with app.app_context():
            a = create_entity(entity_type="note", title="A", actor="user")
            b = create_entity(entity_type="note", title="B", actor="user")
            c = create_entity(entity_type="note", title="C", actor="user")
            create_link(a.id, b.id, link_type="related", actor="user")
            create_link(b.id, c.id, link_type="related", actor="user")
            preview = delete_preview(a.id)
            assert b.id in preview["blocked"]
            assert c.id not in preview["safe_to_cascade"]

    def test_preview_not_found(self, app):
        with app.app_context():
            with pytest.raises(ValueError, match="not found"):
                delete_preview("nonexistent")

    def test_preview_multiple_orphans(self, app):
        with app.app_context():
            parent = create_entity(entity_type="note", title="Parent", actor="user")
            child1 = create_entity(entity_type="note", title="C1", actor="user")
            child2 = create_entity(entity_type="note", title="C2", actor="user")
            create_link(parent.id, child1.id, link_type="related", actor="user")
            create_link(parent.id, child2.id, link_type="related", actor="user")
            preview = delete_preview(parent.id)
            assert child1.id in preview["safe_to_cascade"]
            assert child2.id in preview["safe_to_cascade"]


# ─── V2 API: POST /api/v2/entity-links ───────────────────────────────────────


class TestV2CreateEntityLink:
    def _create_entity(self, **kwargs):
        entity = create_entity(
            entity_type=kwargs.pop("entity_type", "note"),
            title=kwargs.pop("title", "Test"),
            actor="user",
            **kwargs,
        )
        db.session.commit()
        return str(entity.id)

    def test_create_link_success(self, client, app):
        with app.app_context():
            src_id = self._create_entity(title="Src")
            dst_id = self._create_entity(title="Dst")

        res = client.post("/api/v2/entity-links", json={
            "src_id": src_id,
            "dst_id": dst_id,
        })
        assert res.status_code == 201
        data = json.loads(res.data)
        assert "data" in data
        assert data["data"]["src_id"] == src_id
        assert data["data"]["dst_id"] == dst_id
        assert data["data"]["link_type"] == "related"

    def test_create_link_with_type(self, client, app):
        with app.app_context():
            src_id = self._create_entity(title="Src")
            dst_id = self._create_entity(title="Dst")

        res = client.post("/api/v2/entity-links", json={
            "src_id": src_id,
            "dst_id": dst_id,
            "link_type": "references",
        })
        assert res.status_code == 201
        data = json.loads(res.data)
        assert data["data"]["link_type"] == "references"

    def test_create_link_with_metadata(self, client, app):
        with app.app_context():
            src_id = self._create_entity(title="Src")
            dst_id = self._create_entity(title="Dst")

        res = client.post("/api/v2/entity-links", json={
            "src_id": src_id,
            "dst_id": dst_id,
            "source": "ai",
            "confidence": 0.92,
            "evidence": "similar content",
        })
        assert res.status_code == 201
        data = json.loads(res.data)
        assert data["data"]["source"] == "ai"
        assert data["data"]["confidence"] == 0.92
        assert data["data"]["evidence"] == "similar content"

    def test_create_link_missing_fields_returns_400(self, client):
        res = client.post("/api/v2/entity-links", json={"src_id": "abc"})
        assert res.status_code == 400
        data = json.loads(res.data)
        assert "error" in data

    def test_create_link_empty_body_returns_400(self, client):
        res = client.post("/api/v2/entity-links", json={})
        assert res.status_code == 400
        data = json.loads(res.data)
        assert "error" in data

    def test_create_self_link_returns_400(self, client, app):
        with app.app_context():
            entity_id = self._create_entity(title="Self")

        res = client.post("/api/v2/entity-links", json={
            "src_id": entity_id,
            "dst_id": entity_id,
        })
        assert res.status_code == 400
        data = json.loads(res.data)
        assert "error" in data

    def test_create_duplicate_link_returns_400(self, client, app):
        with app.app_context():
            src_id = self._create_entity(title="Src")
            dst_id = self._create_entity(title="Dst")
            create_link(src_id, dst_id, actor="user")

        res = client.post("/api/v2/entity-links", json={
            "src_id": src_id,
            "dst_id": dst_id,
        })
        assert res.status_code == 400
        data = json.loads(res.data)
        assert "error" in data

    def test_create_duplicate_different_type_allowed(self, client, app):
        with app.app_context():
            src_id = self._create_entity(title="Src")
            dst_id = self._create_entity(title="Dst")
            create_link(src_id, dst_id, link_type="related", actor="user")

        res = client.post("/api/v2/entity-links", json={
            "src_id": src_id,
            "dst_id": dst_id,
            "link_type": "references",
        })
        assert res.status_code == 201

    def test_parent_cardinality_enforced_returns_400(self, client, app):
        with app.app_context():
            src_id = self._create_entity(title="Task", entity_type="task")
            dst1_id = self._create_entity(title="P1", entity_type="project")
            dst2_id = self._create_entity(title="P2", entity_type="project")
            create_link(src_id, dst1_id, link_type="parent", actor="user")

        res = client.post("/api/v2/entity-links", json={
            "src_id": src_id,
            "dst_id": dst2_id,
            "link_type": "parent",
        })
        assert res.status_code == 400
        data = json.loads(res.data)
        assert "error" in data

    def test_create_link_entity_not_found_returns_400(self, client, app):
        with app.app_context():
            src_id = self._create_entity(title="Src")

        res = client.post("/api/v2/entity-links", json={
            "src_id": src_id,
            "dst_id": "00000000-0000-0000-0000-000000000000",
        })
        assert res.status_code == 400
        data = json.loads(res.data)
        assert "error" in data


# ─── V2 API: DELETE /api/v2/entity-links/:id ─────────────────────────────────


class TestV2DeleteEntityLink:
    def _create_entity(self, **kwargs):
        entity = create_entity(
            entity_type=kwargs.pop("entity_type", "note"),
            title=kwargs.pop("title", "Test"),
            actor="user",
            **kwargs,
        )
        db.session.commit()
        return str(entity.id)

    def test_delete_link_success(self, client, app):
        with app.app_context():
            src_id = self._create_entity(title="Src")
            dst_id = self._create_entity(title="Dst")
            link = create_link(src_id, dst_id, actor="user")
            link_id = str(link.id)

        res = client.delete(f"/api/v2/entity-links/{link_id}")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["success"] is True

        with app.app_context():
            assert EntityLink.query.get(link.id) is None

    def test_delete_link_not_found_returns_404(self, client):
        res = client.delete("/api/v2/entity-links/00000000-0000-0000-0000-000000000000")
        assert res.status_code == 404
        data = json.loads(res.data)
        assert "error" in data
