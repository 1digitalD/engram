"""Tests for C2-LINKS-API: GET /api/v2/links/:entity_id.

Tests direction-agnostic link queries, link_type filtering,
pagination, and link strength/weight indicators.
"""

import json

from extensions import db
from models import Entity
from services.entity_service import create_entity
from services.link_service import create_link


def _create_entity(**kwargs):
    """Helper to create an entity via service. Returns the entity ID."""
    entity = create_entity(
        entity_type=kwargs.pop("entity_type", "note"),
        title=kwargs.pop("title", "Test"),
        actor="user",
        **kwargs,
    )
    db.session.commit()
    return entity.id


# ─── Basic endpoint ──────────────────────────────────────────────────────────


def test_get_links_entity_not_found(client):
    res = client.get("/api/v2/links/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404
    data = json.loads(res.data)
    assert "error" in data


def test_get_links_no_links_returns_empty(client, app):
    with app.app_context():
        entity_id = _create_entity(title="Lonely")

    res = client.get(f"/api/v2/links/{entity_id}")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["data"] == []
    assert data["total"] == 0
    assert data["limit"] == 50
    assert data["offset"] == 0


def test_get_links_returns_outgoing_links(client, app):
    with app.app_context():
        src_id = _create_entity(title="Src")
        dst1_id = _create_entity(title="Dst1")
        dst2_id = _create_entity(title="Dst2")
        create_link(src_id, dst1_id, actor="user")
        create_link(src_id, dst2_id, link_type="references", actor="user")

    res = client.get(f"/api/v2/links/{src_id}")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["total"] == 2
    assert len(data["data"]) == 2


def test_get_links_returns_incoming_links(client, app):
    with app.app_context():
        src_id = _create_entity(title="Src")
        dst_id = _create_entity(title="Dst")
        create_link(src_id, dst_id, actor="user")

    res = client.get(f"/api/v2/links/{dst_id}")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["total"] == 1
    link = data["data"][0]
    assert link["src_id"] == src_id
    assert link["dst_id"] == dst_id


def test_get_links_direction_agnostic(client, app):
    """Links returned whether entity is src or dst."""
    with app.app_context():
        a_id = _create_entity(title="A")
        b_id = _create_entity(title="B")
        c_id = _create_entity(title="C")
        create_link(a_id, b_id, actor="user")
        create_link(c_id, a_id, actor="user")

    res = client.get(f"/api/v2/links/{a_id}")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["total"] == 2
    ids = {(link["src_id"], link["dst_id"]) for link in data["data"]}
    assert (a_id, b_id) in ids
    assert (c_id, a_id) in ids


# ─── Link strength / weight indicators ───────────────────────────────────────


def test_get_links_returns_weight(client, app):
    with app.app_context():
        src_id = _create_entity(title="Src")
        dst_id = _create_entity(title="Dst")
        create_link(src_id, dst_id, actor="user")

    res = client.get(f"/api/v2/links/{src_id}")
    data = json.loads(res.data)
    assert data["data"][0]["weight"] == 1.0


def test_get_links_returns_confidence(client, app):
    with app.app_context():
        src_id = _create_entity(title="Src")
        dst_id = _create_entity(title="Dst")
        create_link(
            src_id, dst_id, source="ai", confidence=0.87, actor="agent:classify"
        )

    res = client.get(f"/api/v2/links/{src_id}")
    data = json.loads(res.data)
    link = data["data"][0]
    assert link["confidence"] == 0.87
    assert link["source"] == "ai"


def test_get_links_returns_source_and_evidence(client, app):
    with app.app_context():
        src_id = _create_entity(title="Src")
        dst_id = _create_entity(title="Dst")
        create_link(
            src_id, dst_id, source="embedding", confidence=0.92,
            evidence="semantic similarity", actor="agent:autolink"
        )

    res = client.get(f"/api/v2/links/{src_id}")
    data = json.loads(res.data)
    link = data["data"][0]
    assert link["source"] == "embedding"
    assert link["evidence"] == "semantic similarity"
    assert link["confidence"] == 0.92


# ─── Link type filtering ─────────────────────────────────────────────────────


def test_get_links_filter_by_link_type(client, app):
    with app.app_context():
        src_id = _create_entity(title="Src")
        dst1_id = _create_entity(title="Dst1")
        dst2_id = _create_entity(title="Dst2")
        dst3_id = _create_entity(title="Dst3")
        create_link(src_id, dst1_id, link_type="related", actor="user")
        create_link(src_id, dst2_id, link_type="parent", actor="user")
        create_link(src_id, dst3_id, link_type="references", actor="user")

    res = client.get(f"/api/v2/links/{src_id}?link_type=related")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["total"] == 1
    assert data["data"][0]["link_type"] == "related"


def test_get_links_filter_by_link_type_incoming(client, app):
    with app.app_context():
        src_id = _create_entity(title="Src")
        dst_id = _create_entity(title="Dst")
        create_link(src_id, dst_id, link_type="parent", actor="user")
        create_link(dst_id, src_id, link_type="related", actor="user")

    res = client.get(f"/api/v2/links/{src_id}?link_type=parent")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["total"] == 1
    assert data["data"][0]["link_type"] == "parent"
    # src_id is the source in the parent link
    assert data["data"][0]["src_id"] == src_id
    assert data["data"][0]["dst_id"] == dst_id


def test_get_links_no_match_for_filter(client, app):
    with app.app_context():
        src_id = _create_entity(title="Src")
        dst_id = _create_entity(title="Dst")
        create_link(src_id, dst_id, link_type="related", actor="user")

    res = client.get(f"/api/v2/links/{src_id}?link_type=parent")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["total"] == 0
    assert data["data"] == []


# ─── Pagination ──────────────────────────────────────────────────────────────


def test_get_links_pagination_limit(client, app):
    with app.app_context():
        src_id = _create_entity(title="Src")
        for i in range(10):
            dst_id = _create_entity(title=f"Dst{i}")
            create_link(src_id, dst_id, actor="user")

    res = client.get(f"/api/v2/links/{src_id}?limit=3")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert len(data["data"]) == 3
    assert data["total"] == 10
    assert data["limit"] == 3
    assert data["offset"] == 0


def test_get_links_pagination_offset(client, app):
    with app.app_context():
        src_id = _create_entity(title="Src")
        for i in range(10):
            dst_id = _create_entity(title=f"Dst{i}")
            create_link(src_id, dst_id, actor="user")

    res = client.get(f"/api/v2/links/{src_id}?limit=3&offset=6")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert len(data["data"]) == 3
    assert data["total"] == 10
    assert data["offset"] == 6


def test_get_links_pagination_last_page(client, app):
    with app.app_context():
        src_id = _create_entity(title="Src")
        for i in range(5):
            dst_id = _create_entity(title=f"Dst{i}")
            create_link(src_id, dst_id, actor="user")

    res = client.get(f"/api/v2/links/{src_id}?limit=2&offset=4")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert len(data["data"]) == 1
    assert data["total"] == 5
    assert data["offset"] == 4


def test_get_links_default_pagination(client, app):
    with app.app_context():
        src_id = _create_entity(title="Src")
        dst_id = _create_entity(title="Dst")
        create_link(src_id, dst_id, actor="user")

    res = client.get(f"/api/v2/links/{src_id}")
    data = json.loads(res.data)
    assert data["limit"] == 50
    assert data["offset"] == 0


def test_get_links_limit_clamped_to_max(client, app):
    with app.app_context():
        src_id = _create_entity(title="Src")
        dst_id = _create_entity(title="Dst")
        create_link(src_id, dst_id, actor="user")

    res = client.get(f"/api/v2/links/{src_id}?limit=99999")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["limit"] == 1000


def test_get_links_limit_minimum(client, app):
    with app.app_context():
        src_id = _create_entity(title="Src")
        dst_id = _create_entity(title="Dst")
        create_link(src_id, dst_id, actor="user")

    res = client.get(f"/api/v2/links/{src_id}?limit=0")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["limit"] == 1


# ─── Link includes other entity data ─────────────────────────────────────────


def test_get_links_includes_direction_field(client, app):
    """Each link indicates whether the queried entity is src or dst."""
    with app.app_context():
        a_id = _create_entity(title="A")
        b_id = _create_entity(title="B")
        create_link(a_id, b_id, actor="user")

    res = client.get(f"/api/v2/links/{a_id}")
    data = json.loads(res.data)
    assert data["data"][0]["direction"] == "outgoing"

    res = client.get(f"/api/v2/links/{b_id}")
    data = json.loads(res.data)
    assert data["data"][0]["direction"] == "incoming"


def test_get_links_includes_other_entity(client, app):
    """Each link includes the other entity's basic info."""
    with app.app_context():
        src_id = _create_entity(title="Source Note", entity_type="note")
        dst_id = _create_entity(title="Target Task", entity_type="task")
        create_link(src_id, dst_id, actor="user")

    res = client.get(f"/api/v2/links/{src_id}")
    data = json.loads(res.data)
    link = data["data"][0]
    assert "other_entity" in link
    other = link["other_entity"]
    assert other["id"] == dst_id
    assert other["title"] == "Target Task"
    assert other["type"] == "task"


def test_get_links_mixed_directions_with_other_entity(client, app):
    with app.app_context():
        a_id = _create_entity(title="A")
        b_id = _create_entity(title="B")
        c_id = _create_entity(title="C")
        create_link(a_id, b_id, actor="user")
        create_link(c_id, a_id, actor="user")

    res = client.get(f"/api/v2/links/{a_id}")
    data = json.loads(res.data)
    assert data["total"] == 2

    outgoing = [l for l in data["data"] if l["direction"] == "outgoing"]
    incoming = [l for l in data["data"] if l["direction"] == "incoming"]
    assert len(outgoing) == 1
    assert len(incoming) == 1
    assert outgoing[0]["other_entity"]["title"] == "B"
    assert incoming[0]["other_entity"]["title"] == "C"
