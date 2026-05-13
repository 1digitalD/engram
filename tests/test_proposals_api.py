import json

from extensions import db
from models import Entity, EntityLink
from services.entity_service import create_entity


def _create_entity(**kwargs):
    entity = create_entity(
        entity_type=kwargs.pop("entity_type", "note"),
        title=kwargs.pop("title", "Test"),
        actor="user",
        **kwargs,
    )
    db.session.commit()
    return str(entity.id)


def test_v2_proposals_lists_entity_link_proposals(client, app):
    with app.app_context():
        note_id = _create_entity(
            entity_type="note",
            title="Source note",
            content="# Source note",
        )
        note = db.session.get(Entity, note_id)
        note.ai_meta = {
            "link_proposals": [
                {
                    "dst_id": "00000000-0000-0000-0000-000000000222",
                    "confidence": 0.88,
                    "link_type": "related",
                },
            ],
        }
        target = Entity(
            id="00000000-0000-0000-0000-000000000222",
            type="project",
            title="Apollo",
            content="Project Apollo",
            status="active",
            lifecycle="active",
            properties={},
            ai_meta={},
            ai_status="done",
        )
        db.session.add(target)
        db.session.commit()

    res = client.get(f"/api/v2/proposals?entity_id={note_id}")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert len(data["data"]) == 1
    proposal = data["data"][0]
    assert proposal["src_id"] == note_id
    assert proposal["dst_id"] == "00000000-0000-0000-0000-000000000222"
    assert proposal["confidence"] == 0.88
    assert proposal["other_entity"] == {
        "id": "00000000-0000-0000-0000-000000000222",
        "title": "Apollo",
        "type": "project",
    }


def test_v2_links_post_creates_entity_link(client, app):
    with app.app_context():
        src_id = _create_entity(entity_type="note", title="Source")
        dst_id = _create_entity(entity_type="project", title="Target")

    res = client.post(
        "/api/v2/links",
        json={
            "src_id": src_id,
            "dst_id": dst_id,
            "link_type": "related",
        },
    )
    assert res.status_code == 201
    data = json.loads(res.data)
    assert data["data"]["src_id"] == src_id
    assert data["data"]["dst_id"] == dst_id

    with app.app_context():
        links = EntityLink.query.all()
        assert len(links) == 1
        assert str(links[0].src_id) == src_id
        assert str(links[0].dst_id) == dst_id
