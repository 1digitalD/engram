from extensions import db
from models import AiSuggestion, Entity, EntityEvent


def test_agent_activity_returns_events_suggestions_and_failures(client, app):
    note_response = client.post("/api/v4/entities", json={"type": "note", "title": "Source note", "content": "Body"})
    assert note_response.status_code == 201
    note_id = note_response.get_json()["data"]["id"]

    with app.app_context():
        note = db.session.get(Entity, note_id)
        note.ai_status = "failed"
        event = EntityEvent(
            entity_id=note.id,
            event_type="ai_updated",
            actor="agent:v4-capture",
            confidence=0.91,
            reason="summary updated",
        )
        suggestion = AiSuggestion(
            source_entity_id=note.id,
            suggestion_type="create_task",
            operation_type="create_entity",
            payload={"type": "task", "title": "Follow up"},
            confidence=0.64,
            reason="low confidence task",
            status="pending",
        )
        db.session.add_all([event, suggestion])
        db.session.commit()

    response = client.get("/api/v4/agent-activity")

    assert response.status_code == 200
    payload = response.get_json()
    categories = {item["category"] for item in payload["data"]}
    assert {"auto_applied", "suggested", "failed"}.issubset(categories)
    assert payload["meta"]["counts"]["auto_applied"] == 1
    assert payload["meta"]["counts"]["suggested"] == 1
    assert payload["meta"]["counts"]["failed"] == 1
    event_item = next(item for item in payload["data"] if item["category"] == "auto_applied")
    assert event_item["entity"]["title"] == "Source note"
    assert event_item["confidence"] == 0.91
