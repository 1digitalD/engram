"""Cycle 5 tests for v4 keyword, semantic, and hybrid search."""

from unittest.mock import patch

from extensions import db
from models import EntityChunk


def _create_entity(client, entity_type, title, content="", **extra):
    payload = {"type": entity_type, "title": title, "content": content}
    payload.update(extra)
    response = client.post("/api/v4/entities", json=payload)
    assert response.status_code == 201
    return response.get_json()["data"]


def _add_chunk(entity_id, text, embedding):
    db.session.add(
        EntityChunk(
            entity_id=entity_id,
            chunk_index=0,
            chunk_text=text,
            embedding=embedding,
            embedding_model="test",
        )
    )
    db.session.commit()


def test_keyword_search(client):
    _create_entity(client, "note", "Memory rollout", "Feature flags and rollback plan")
    _create_entity(client, "task", "Buy milk", "Grocery list")

    response = client.get("/api/v4/search?q=rollback&mode=keyword")

    assert response.status_code == 200
    data = response.get_json()
    assert data["mode"] == "keyword"
    assert [row["entity"]["title"] for row in data["results"]] == ["Memory rollout"]
    assert data["results"][0]["match"]["keyword_rank"] == 1


def test_semantic_search_with_mocked_embeddings(client, app):
    memory = _create_entity(client, "note", "Memory rollout", "Feature flags")
    groceries = _create_entity(client, "task", "Buy milk", "Grocery list")
    with app.app_context():
        _add_chunk(memory["id"], "deployment safety", [1.0] + [0.0] * 1535)
        _add_chunk(groceries["id"], "milk eggs", [0.0, 1.0] + [0.0] * 1534)

    with patch("services.embeddings._embed_texts", return_value=[[1.0] + [0.0] * 1535]):
        response = client.get("/api/v4/search?q=deployment&mode=semantic")

    assert response.status_code == 200
    data = response.get_json()
    assert data["mode"] == "semantic"
    assert data["results"][0]["entity"]["id"] == memory["id"]
    assert data["results"][0]["match"]["semantic_rank"] == 1


def test_hybrid_search_uses_rrf(client, app):
    keyword = _create_entity(client, "note", "Memory rollout", "Feature flags")
    semantic = _create_entity(client, "resource", "Deployment guide", "Safety checklist")
    with app.app_context():
        _add_chunk(keyword["id"], "rollout", [0.0, 1.0] + [0.0] * 1534)
        _add_chunk(semantic["id"], "deployment safety", [1.0] + [0.0] * 1535)

    with patch("services.embeddings._embed_texts", return_value=[[1.0] + [0.0] * 1535]):
        response = client.get("/api/v4/search?q=memory&mode=hybrid")

    assert response.status_code == 200
    data = response.get_json()
    assert data["mode"] == "hybrid"
    assert {row["entity"]["id"] for row in data["results"]} == {keyword["id"], semantic["id"]}
    assert all(row["score"] > 0 for row in data["results"])


def test_search_filters(client):
    _create_entity(client, "note", "Memory rollout", "Feature flags")
    _create_entity(client, "task", "Memory task", "Feature flags", status="waiting")
    archived = _create_entity(client, "task", "Memory archived", "Feature flags")
    client.patch(f"/api/v4/entities/{archived['id']}", json={"lifecycle": "archived"})

    response = client.get("/api/v4/search?q=memory&type=task&status=waiting&lifecycle=active")

    assert response.status_code == 200
    results = response.get_json()["results"]
    assert len(results) == 1
    assert results[0]["entity"]["type"] == "task"
    assert results[0]["entity"]["status"] == "waiting"


def test_embed_backfill_cli_embeds_active_entities_without_chunks(client, runner, app):
    needs_embedding = _create_entity(client, "note", "Needs embedding", "Memory rollout")
    already_embedded = _create_entity(client, "task", "Already embedded", "Task")
    deleted = _create_entity(client, "project", "Deleted project", "Project")
    client.delete(f"/api/v4/entities/{deleted['id']}")

    with app.app_context():
        _add_chunk(already_embedded["id"], "existing chunk", [0.0] * 1536)

    with patch("services.embeddings.embed_entity") as mock_embed:
        result = runner.invoke(args=["embed-backfill"])

    assert result.exit_code == 0
    assert "Embedded 1 entities." in result.output
    assert [call.args[0] for call in mock_embed.call_args_list] == [needs_embedding["id"]]
