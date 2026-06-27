import json

from services import v4_extraction


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Response:
    def __init__(self, payload):
        self.choices = [_Choice(json.dumps(payload))]


class _Completions:
    def __init__(self, payload, calls):
        self.payload = payload
        self.calls = calls

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response(self.payload)


class _Chat:
    def __init__(self, payload, calls):
        self.completions = _Completions(payload, calls)


class _Client:
    def __init__(self, payload, calls):
        self.chat = _Chat(payload, calls)


def test_extraction_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert v4_extraction.extract_capture_candidates("Ask Henry about launch") == {}


def test_extraction_calls_openai_and_normalizes_candidates(monkeypatch):
    calls = []
    payload = {
        "summary": "Discuss rollout with Henry.",
        "confidence": 2,
        "tags": ["Rollout", {"name": "AI", "confidence": "0.8"}],
        "links": [
            {
                "target_type": "person",
                "title": "Henry",
                "relationship_type": "mentions",
                "confidence": 0.92,
                "evidence": "Ask Henry",
            },
            {"target_type": "note", "title": "Invalid target"},
        ],
        "entities": [
            {"type": "task", "title": "Ask Henry about launch", "confidence": 0.7},
            {"type": "note", "title": "Do not convert notes"},
        ],
    }
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ENGRAM_ALLOW_TEST_AI", "1")
    monkeypatch.setattr(v4_extraction, "get_openai_client", lambda: _Client(payload, calls))

    result = v4_extraction.extract_capture_candidates("Ask Henry about launch")

    assert calls[0]["response_format"] == {"type": "json_object"}
    assert result["summary"] == "Discuss rollout with Henry."
    assert result["confidence"] == 1.0
    assert result["tags"] == [
        {"name": "Rollout", "confidence": 0.6},
        {"name": "AI", "confidence": 0.8},
    ]
    assert result["links"] == [{
        "target_type": "person",
        "title": "Henry",
        "relationship_type": "mentions",
        "confidence": 0.92,
        "evidence": "Ask Henry",
    }]
    assert result["entities"] == [{
        "type": "task",
        "title": "Ask Henry about launch",
        "content": None,
        "due_at": None,
        "follow_up_at": None,
        "assigned_to": None,
        "confidence": 0.7,
        "evidence": None,
    }]


def test_normalization_unescapes_html_entities():
    from services.v4_extraction import normalize_candidates

    result = normalize_candidates({
        "title": "Resourcing &amp; Team Health",
        "entities": [{
            "type": "project",
            "title": "R&amp;D &quot;north star&quot; planning",
            "confidence": 0.9,
            "evidence": "teams said they were &quot;blocked&quot;",
        }],
        "tags": [{"name": "q3&amp;q4", "confidence": 0.8}],
    })

    assert result["title"] == "Resourcing & Team Health"
    assert result["entities"][0]["title"] == 'R&D "north star" planning'
    assert result["entities"][0]["evidence"] == 'teams said they were "blocked"'
    assert result["tags"][0]["name"] == "q3&q4"


def test_normalization_leaves_plain_ampersands_alone():
    from services.v4_extraction import normalize_candidates

    result = normalize_candidates({
        "title": "Q&A session prep",
        "entities": [],
        "tags": [],
    })
    assert result["title"] == "Q&A session prep"


def test_recent_existing_entities_includes_active_tasks(client, app):
    task_resp = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Follow up with Akash about Q3", "status": "open"},
    )
    assert task_resp.status_code == 201
    project_resp = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "Agent convergence", "status": "active"},
    )
    assert project_resp.status_code == 201

    with app.app_context():
        result = v4_extraction._recent_existing_entities()

    assert "Agent convergence" in result["project"]
    assert "Follow up with Akash about Q3" in result["task"]
    assert len(result["task"]) <= v4_extraction.TASK_RECENT_LIMIT


def test_recent_existing_entities_excludes_done_tasks(client, app):
    client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Done task", "status": "done"},
    )
    client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Open task", "status": "open"},
    )
    client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Archived task", "status": "open", "lifecycle": "archived"},
    )
    client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Deleted task", "status": "open", "lifecycle": "deleted"},
    )

    with app.app_context():
        result = v4_extraction._recent_existing_entities()

    titles = result["task"]
    assert "Open task" in titles
    assert "Done task" not in titles
    assert "Archived task" not in titles
    assert "Deleted task" not in titles


def test_format_existing_entities_block_includes_tasks_section():
    existing = {
        "project": ["Agent convergence"],
        "task": ["Follow up with Akash about Q3", "Draft project plan"],
        "area": ["Work"],
    }
    block = v4_extraction._format_existing_entities_block(existing)

    assert "Recent Active Open Tasks:" in block
    assert "- Follow up with Akash about Q3" in block
    assert "- Draft project plan" in block
    projects_pos = block.index("Projects:")
    tasks_pos = block.index("Recent Active Open Tasks:")
    areas_pos = block.index("Areas:")
    assert projects_pos < tasks_pos < areas_pos
