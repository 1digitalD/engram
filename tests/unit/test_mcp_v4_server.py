import httpx
import pytest

from mcp_server import server


def test_search_entities_calls_v4_search(monkeypatch):
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {
            "results": [{
                "entity": {"id": "p1", "type": "project", "title": "Memory Lookup"},
                "score": 0.75,
                "match": {"snippet": "v4 rollout"},
            }]
        }

    monkeypatch.setattr(server, "_api", fake_api)

    text = server.search_entities(
        "memory",
        entity_type="project",
        mode="semantic",
        status="active",
        lifecycle="archived",
        tag="ops",
        limit=999,
    )

    assert calls == [(
        "GET",
        "/search",
        {"params": {
            "q": "memory",
            "mode": "semantic",
            "limit": 50,
            "type": "project",
            "status": "active",
            "lifecycle": "archived",
            "tag": "ops",
        }},
    )]
    assert "Memory Lookup" in text


def test_search_entities_supports_tag_only_queries(monkeypatch):
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"results": []}

    monkeypatch.setattr(server, "_api", fake_api)

    text = server.search_entities(query="", tag="ops")

    assert calls == [(
        "GET",
        "/search",
        {"params": {"mode": "hybrid", "limit": 10, "lifecycle": "active", "tag": "ops"}},
    )]
    assert "tag:ops" in text


def test_get_entity_uses_detail_by_default(monkeypatch):
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {
            "entity": {"id": "t1", "type": "task", "title": "Follow up", "status": "open", "lifecycle": "active"},
            "sections": [],
        }

    monkeypatch.setattr(server, "_api", fake_api)

    text = server.get_entity("t1")

    assert calls == [("GET", "/entities/t1/detail", {})]
    assert "Follow up" in text


def test_list_recent_clamps_limit_and_filters_type(monkeypatch):
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"data": [{"id": "n1", "type": "note", "title": "Captured note"}]}

    monkeypatch.setattr(server, "_api", fake_api)

    text = server.list_recent(entity_type="note", limit=0)

    assert calls == [("GET", "/recent", {"params": {"limit": 1, "type": "note"}})]
    assert "Captured note" in text


def test_api_reports_unreachable_api(monkeypatch):
    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, **kwargs):
            raise httpx.ConnectError("offline")

    monkeypatch.setattr(server.httpx, "Client", FakeClient)

    with pytest.raises(RuntimeError, match="unreachable"):
        server._api("GET", "/recent")


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


def test_get_today_returns_formatted_snapshot(monkeypatch):
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path))
        return {
            "follow_ups": [{
                "id": "t1",
                "type": "task",
                "title": "Call dentist",
                "follow_up_at": "2025-06-01",
                "attention": {
                    "score": 52,
                    "level": "high",
                    "reasons": [{"key": "follow_up:today", "label": "follow-up today"}],
                },
            }],
            "blocked_or_waiting_tasks": [],
            "projects_without_open_tasks": [{"id": "p1", "type": "project", "title": "Website"}],
            "recent_notes": [],
            "pending_suggestions": [{"id": "s1", "suggestion_type": "create_task", "reason": "make slides"}],
        }

    monkeypatch.setattr(server, "_api", fake_api)
    text = server.get_today()

    assert calls == [("GET", "/today")]
    assert "Call dentist" in text
    assert "attention=high:52, follow-up today" in text
    assert "Website" in text
    assert "make slides" in text


def test_get_today_nothing_pending(monkeypatch):
    monkeypatch.setattr(server, "_api", lambda *a, **kw: {
        "follow_ups": [],
        "blocked_or_waiting_tasks": [],
        "projects_without_open_tasks": [],
        "recent_notes": [],
        "pending_suggestions": [],
    })
    assert server.get_today() == "Nothing due or pending today."


def test_list_suggestions_calls_api_with_status(monkeypatch):
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"data": [
            {"id": "s1", "suggestion_type": "create_task", "confidence": 0.85,
             "source_note_title": "Meeting notes", "reason": "add slides"},
        ]}

    monkeypatch.setattr(server, "_api", fake_api)
    text = server.list_suggestions(status="pending")

    assert calls == [("GET", "/suggestions", {"params": {"status": "pending"}})]
    assert "create_task" in text
    assert "Meeting notes" in text


def test_get_agent_activity_returns_formatted_audit_log(monkeypatch):
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {
            "data": [{
                "id": "e1",
                "category": "auto_applied",
                "event_type": "ai_updated",
                "actor": "agent:v4-capture",
                "confidence": 0.91,
                "reason": "summary updated",
                "entity": {"id": "n1", "type": "note", "title": "Source note"},
            }]
        }

    monkeypatch.setattr(server, "_api", fake_api)
    text = server.get_agent_activity(limit=5)

    assert calls == [("GET", "/agent-activity", {"params": {"limit": 5}})]
    assert "auto_applied" in text
    assert "Source note" in text
    assert "confidence=0.91" in text


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------


def test_capture_posts_content_and_source(monkeypatch):
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {
            "source_note": {"id": "n1", "title": "Team standup"},
            "applied_changes": [{"type": "tag_added", "tag": "meeting"}],
            "suggestions": [],
            "warnings": [],
        }

    monkeypatch.setattr(server, "_api", fake_api)
    text = server.capture("Team standup notes", source="slack")

    assert calls == [("POST", "/capture", {"json": {"content": "Team standup notes", "source": "slack"}})]
    assert "n1" in text
    assert "tag: meeting" in text


def test_capture_omits_source_when_none(monkeypatch):
    def fake_api(method, path, **kwargs):
        return {"source_note": {"id": "n2", "title": "Quick note"}, "applied_changes": [], "suggestions": [], "warnings": []}

    monkeypatch.setattr(server, "_api", fake_api)
    server.capture("Quick note")


def test_create_entity_posts_correct_body(monkeypatch):
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"data": {"id": "t1", "type": "task", "title": "Write tests", "status": "open"}}

    monkeypatch.setattr(server, "_api", fake_api)
    text = server.create_entity("task", "Write tests", tags=["engineering"], due_at="2025-07-01")

    assert calls == [(
        "POST", "/entities",
        {"json": {"type": "task", "title": "Write tests", "tags": ["engineering"], "due_at": "2025-07-01"}},
    )]
    assert "t1" in text
    assert "Write tests" in text


def test_update_entity_sends_only_provided_fields(monkeypatch):
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"data": {"id": "t1", "type": "task", "title": "Write tests", "status": "done"}}

    monkeypatch.setattr(server, "_api", fake_api)
    text = server.update_entity("t1", status="done")

    assert calls == [("PATCH", "/entities/t1", {"json": {"status": "done"}})]
    assert "done" in text


def test_update_entity_returns_error_when_no_fields(monkeypatch):
    monkeypatch.setattr(server, "_api", lambda *a, **kw: {})
    result = server.update_entity("t1")
    assert "No fields" in result


def test_link_entities_posts_relationship(monkeypatch):
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"data": {"id": "r1", "source_entity_id": "t1", "target_entity_id": "p1", "relationship_type": "parent"}}

    monkeypatch.setattr(server, "_api", fake_api)
    text = server.link_entities("t1", "p1", relationship_type="parent", evidence="explicitly stated")

    assert calls == [(
        "POST", "/entities/t1/relationships",
        {"json": {"target_entity_id": "p1", "relationship_type": "parent", "evidence": "explicitly stated"}},
    )]
    assert "t1" in text
    assert "p1" in text


def test_accept_suggestion_calls_correct_endpoint(monkeypatch):
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path))
        return {
            "suggestion": {"id": "s1", "status": "accepted"},
            "created_entity": {"id": "t9", "type": "task", "title": "Buy milk"},
            "relationship": None,
        }

    monkeypatch.setattr(server, "_api", fake_api)
    text = server.accept_suggestion("s1")

    assert calls == [("POST", "/suggestions/s1/accept")]
    assert "accepted" in text
    assert "Buy milk" in text


def test_dismiss_suggestion_calls_correct_endpoint(monkeypatch):
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path))
        return {"suggestion": {"id": "s2", "status": "dismissed"}, "created_entity": None, "relationship": None}

    monkeypatch.setattr(server, "_api", fake_api)
    text = server.dismiss_suggestion("s2")

    assert calls == [("POST", "/suggestions/s2/dismiss")]
    assert "dismissed" in text


def test_reconcile_suggestions_calls_correct_endpoint(monkeypatch):
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {
            "data": [{"id": "s9", "suggestion_type": "create_task", "reason": "relationship already exists"}],
            "meta": {"scanned": 4, "expired": 1},
        }

    monkeypatch.setattr(server, "_api", fake_api)
    text = server.reconcile_suggestions(limit=25)

    assert calls == [("POST", "/suggestions/reconcile", {"params": {"limit": 25}})]
    assert "scanned=4" in text
    assert "expired=1" in text
    assert "s9" in text


def test_submit_candidates_posts_to_ingest_endpoint(monkeypatch):
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {
            "source_note": {"id": "n1", "title": "Meeting"},
            "applied_changes": [{"type": "entity_created", "entity_type": "task", "entity_id": "t2", "title": "Follow up"}],
            "suggestions": [],
            "warnings": [],
        }

    monkeypatch.setattr(server, "_api", fake_api)
    text = server.submit_candidates(
        entity_id="n1",
        summary="Team sync",
        entities=[{"type": "task", "title": "Follow up", "confidence": 0.95, "evidence": "needs follow up"}],
    )

    assert calls[0][:2] == ("POST", "/entities/n1/ingest_candidates")
    body = calls[0][2]["json"]
    assert body["summary"] == "Team sync"
    assert body["entities"][0]["title"] == "Follow up"
    assert "Follow up" in text


def test_submit_candidates_defaults_empty_lists(monkeypatch):
    def fake_api(method, path, **kwargs):
        body = kwargs["json"]
        assert body["tags"] == []
        assert body["entities"] == []
        assert body["links"] == []
        return {"source_note": {"id": "n1", "title": "X"}, "applied_changes": [], "suggestions": [], "warnings": []}

    monkeypatch.setattr(server, "_api", fake_api)
    server.submit_candidates("n1")


def test_append_activity_update_passes_skip_extraction(monkeypatch):
    calls = []

    def fake_api(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {
            "data": {"id": "n1", "content": "Logged progress"},
            "extracted": {},
            "suggestions": [],
        }

    monkeypatch.setattr(server, "_api", fake_api)
    server.append_activity_update("p1", "Logged progress", skip_extraction=True)

    assert calls[0][:2] == ("POST", "/entities/p1/activity_updates")
    assert calls[0][2]["json"] == {"content": "Logged progress", "skip_extraction": True}
