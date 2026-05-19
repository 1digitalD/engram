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

    text = server.search_entities("memory", entity_type="project", limit=999)

    assert calls == [(
        "GET",
        "/search",
        {"params": {"q": "memory", "mode": "hybrid", "limit": 50, "type": "project"}},
    )]
    assert "Memory Lookup" in text


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
