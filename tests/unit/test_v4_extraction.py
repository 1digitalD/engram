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
