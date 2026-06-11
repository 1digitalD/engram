"""Tests for entity merge and project↔task type conversion."""

from models import AiSuggestion, Entity, EntityEvent, EntityLink, EntityTag, Job, Tag
from extensions import db


def _create(client, **kwargs):
    response = client.post("/api/v4/entities", json=kwargs)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def _link(app, source_id, target_id, relationship_type="related"):
    with app.app_context():
        db.session.add(EntityLink(
            source_entity_id=source_id,
            target_entity_id=target_id,
            relationship_type=relationship_type,
        ))
        db.session.commit()


# ── Merge ─────────────────────────────────────────────────────────────────────

def test_merge_repoints_links_and_tombstones_loser(client, app):
    survivor = _create(client, type="project", title="Define Agent Platform roadmap")
    loser = _create(client, type="project", title="Plan agent platform roadmap", content="roadmap details")
    task = _create(client, type="task", title="Draft roadmap doc")
    note = _create(client, type="note", title="Roadmap note", content="notes")

    _link(app, task["id"], loser["id"], "parent")      # incoming: task under dup project
    _link(app, loser["id"], note["id"], "mentions")    # outgoing: dup project mentions note

    response = client.post(f"/api/v4/entities/{loser['id']}/merge", json={"target_id": survivor["id"]})
    assert response.status_code == 200
    body = response.get_json()
    assert body["data"]["id"] == survivor["id"]
    assert body["merge"]["links_moved"] == 2
    assert body["merge"]["links_dropped"] == 0
    assert "content" in body["merge"]["fields_copied"]

    with app.app_context():
        merged = db.session.get(Entity, loser["id"])
        assert merged.lifecycle == "deleted"
        assert merged.properties["merged_into"] == survivor["id"]

        assert EntityLink.query.filter_by(
            source_entity_id=task["id"], target_entity_id=survivor["id"], relationship_type="parent"
        ).count() == 1
        assert EntityLink.query.filter_by(
            source_entity_id=survivor["id"], target_entity_id=note["id"], relationship_type="mentions"
        ).count() == 1
        assert EntityLink.query.filter(
            (EntityLink.source_entity_id == loser["id"]) | (EntityLink.target_entity_id == loser["id"])
        ).count() == 0

        # survivor backfilled content it was missing
        kept = db.session.get(Entity, survivor["id"])
        assert kept.content == "roadmap details"

        assert EntityEvent.query.filter_by(entity_id=survivor["id"], event_type="merged").count() == 1
        assert EntityEvent.query.filter_by(entity_id=loser["id"], event_type="merged_into").count() == 1

        # survivor re-embed queued
        assert Job.query.filter_by(entity_id=survivor["id"], job_type="embed", status="pending").count() >= 1


def test_merge_drops_duplicate_and_self_links(client, app):
    survivor = _create(client, type="project", title="Telemetry")
    loser = _create(client, type="project", title="Telemetry rollout")
    note = _create(client, type="note", title="Note", content="x")

    _link(app, survivor["id"], note["id"], "mentions")  # survivor already has it
    _link(app, loser["id"], note["id"], "mentions")     # duplicate after re-point
    _link(app, loser["id"], survivor["id"], "related")  # would become self-link

    response = client.post(f"/api/v4/entities/{loser['id']}/merge", json={"target_id": survivor["id"]})
    assert response.status_code == 200
    assert response.get_json()["merge"]["links_dropped"] == 2

    with app.app_context():
        assert EntityLink.query.filter_by(source_entity_id=survivor["id"], target_entity_id=survivor["id"]).count() == 0


def test_merge_unions_tags(client, app):
    survivor = _create(client, type="task", title="Ship rollout", tags=["rollout"])
    loser = _create(client, type="task", title="Ship the rollout", tags=["rollout", "urgent"])

    response = client.post(f"/api/v4/entities/{loser['id']}/merge", json={"target_id": survivor["id"]})
    assert response.status_code == 200
    assert response.get_json()["merge"]["tags_moved"] == 1

    with app.app_context():
        survivor_tags = {
            t.name
            for t in Tag.query.join(EntityTag, EntityTag.tag_id == Tag.id)
            .filter(EntityTag.entity_id == survivor["id"]).all()
        }
        assert survivor_tags == {"rollout", "urgent"}
        assert EntityTag.query.filter_by(entity_id=loser["id"]).count() == 0


def test_merge_repoints_pending_suggestions(client, app):
    survivor = _create(client, type="project", title="Roadmap")
    loser = _create(client, type="project", title="Roadmap v2")
    with app.app_context():
        db.session.add(AiSuggestion(
            source_entity_id=loser["id"],
            suggestion_type="update_project",
            operation_type="update_entity",
            payload={"target_entity_id": loser["id"], "fields": {"status": "on_hold"}},
        ))
        db.session.commit()

    response = client.post(f"/api/v4/entities/{loser['id']}/merge", json={"target_id": survivor["id"]})
    assert response.status_code == 200

    with app.app_context():
        suggestion = AiSuggestion.query.one()
        assert suggestion.source_entity_id == survivor["id"]
        assert suggestion.payload["target_entity_id"] == survivor["id"]


def test_merge_validations(client, app):
    project = _create(client, type="project", title="P")
    task = _create(client, type="task", title="T")

    assert client.post(f"/api/v4/entities/{project['id']}/merge", json={}).status_code == 400
    assert client.post(
        f"/api/v4/entities/{project['id']}/merge", json={"target_id": project["id"]}
    ).status_code == 400
    assert client.post(
        f"/api/v4/entities/{project['id']}/merge", json={"target_id": task["id"]}
    ).status_code == 400
    assert client.post(
        f"/api/v4/entities/{project['id']}/merge", json={"target_id": "nonexistent"}
    ).status_code == 404

    # already-merged loser can't merge again
    other = _create(client, type="project", title="P2")
    client.post(f"/api/v4/entities/{other['id']}/merge", json={"target_id": project["id"]})
    assert client.post(
        f"/api/v4/entities/{other['id']}/merge", json={"target_id": project["id"]}
    ).status_code == 400


# ── Type conversion ───────────────────────────────────────────────────────────

def test_convert_project_to_task(client, app):
    project = _create(client, type="project", title="Agent Platform leadership deck")
    client.patch(f"/api/v4/entities/{project['id']}", json={"status": "on_hold"})

    response = client.post(f"/api/v4/entities/{project['id']}/convert", json={"type": "task"})
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["type"] == "task"
    assert data["status"] == "waiting"

    with app.app_context():
        assert EntityEvent.query.filter_by(entity_id=project["id"], event_type="type_converted").count() == 1


def test_convert_project_with_children_is_blocked(client, app):
    project = _create(client, type="project", title="Real project")
    task = _create(client, type="task", title="Child task")
    _link(app, task["id"], project["id"], "parent")

    response = client.post(f"/api/v4/entities/{project['id']}/convert", json={"type": "task"})
    assert response.status_code == 400
    assert "child" in response.get_json()["error"]


def test_convert_task_to_project(client, app):
    task = _create(client, type="task", title="Build evals infrastructure")
    client.patch(f"/api/v4/entities/{task['id']}", json={"status": "done"})

    response = client.post(f"/api/v4/entities/{task['id']}/convert", json={"type": "project"})
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["type"] == "project"
    assert data["status"] == "completed"


def test_convert_unsupported_type(client, app):
    note = _create(client, type="note", title="A note", content="x")
    response = client.post(f"/api/v4/entities/{note['id']}/convert", json={"type": "task"})
    assert response.status_code == 400
