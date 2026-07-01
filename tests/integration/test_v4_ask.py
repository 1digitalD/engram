"""Integration tests for /api/v4/ask grounded Q&A."""

from unittest.mock import patch

from extensions import db
from models import EntityChunk
from services import v4_ask


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


def test_ask_returns_grounded_answer(client, app):
    v4_ask._clear_cache()
    note = _create_entity(
        client,
        "note",
        "Mary's PR review feedback",
        "Mary said the PR review looked good and asked to add more tests.",
    )
    with app.app_context():
        _add_chunk(
            note["id"],
            "Mary said the PR review looked good and asked to add more tests.",
            [1.0] + [0.0] * 1535,
        )

    with patch("services.embeddings._embed_texts", return_value=[[1.0] + [0.0] * 1535]):
        response = client.post(
            "/api/v4/ask",
            json={"question": "What did Mary say about the PR review?"},
        )

    assert response.status_code == 200
    data = response.get_json()
    assert "answer" in data
    assert data["answer"]
    assert data["confidence"] in ("high", "medium")
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["entity_id"] == note["id"]
    assert "snippet" in data["citations"][0]
    assert "relevance" in data["citations"][0]
    assert data["caveats"] == []
    assert any(action["type"] == "open" for action in data["suggested_actions"])


def test_ask_returns_low_confidence_when_no_context(client):
    v4_ask._clear_cache()
    response = client.post(
        "/api/v4/ask",
        json={"question": "What did Mary say about the PR review?"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["answer"] == "I don't have anything in the workspace that answers this."
    assert data["confidence"] == "low"
    assert data["citations"] == []
    assert data["caveats"]
    assert any(
        action["type"] == "capture" and action["label"] == "Capture starting point"
        for action in data["suggested_actions"]
    )


def test_ask_includes_citations(client, app):
    v4_ask._clear_cache()
    note = _create_entity(
        client,
        "note",
        "Mary's PR review feedback",
        "Mary said the PR review looked good.",
    )
    with app.app_context():
        _add_chunk(note["id"], "Mary said the PR review looked good.", [1.0] + [0.0] * 1535)

    with patch("services.embeddings._embed_texts", return_value=[[1.0] + [0.0] * 1535]):
        response = client.post(
            "/api/v4/ask",
            json={"question": "What did Mary say about the PR review?"},
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data["citations"]
    for citation in data["citations"]:
        assert set(citation.keys()) >= {"entity_id", "snippet", "relevance"}
        assert isinstance(citation["relevance"], float)


def test_ask_low_confidence_state_does_not_confabulate(client):
    v4_ask._clear_cache()
    _create_entity(client, "note", "Grocery list", "Buy milk and eggs.")

    response = client.post(
        "/api/v4/ask",
        json={"question": "What did Mary say about the PR review?"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["answer"] == "I don't have anything in the workspace that answers this."
    assert data["confidence"] == "low"
    assert data["citations"] == []


def test_ask_weak_citations_does_not_confabulate_b017(client, app):
    """B-017 regression test: when search returns weak citations (max
    relevance below WEAK_RELEVANCE=0.5), Ask ✦ must still say IDK instead
    of dumping the citations into a fallback answer.

    The previous code returned 'medium' for any non-empty citations list,
    which let _fallback_answer dump unrelated snippets as if they answered
    the question. This test ensures the IDK path fires for unanswerable
    questions like 'What is the capital of Mars?' even when the search
    happens to return weak matches.
    """
    v4_ask._clear_cache()
    # Create a note with content that's tangentially related to the question
    # but unlikely to be a strong match. Use a low-relevance embedding to
    # force the search to return this note with relevance < 0.5.
    note = _create_entity(
        client,
        "note",
        "Mars exploration context",
        "NASA's Mars rover program has been ongoing for decades.",
    )
    with app.app_context():
        # Embedding is the opposite of the query vector, so cosine sim is low.
        _add_chunk(note["id"], "NASA Mars rover.", [-1.0] + [0.0] * 1535)

    # Query with an embedding close to [1, 0, 0, ...] so sim with [-1, 0, ...] is -1.
    with patch("services.embeddings._embed_texts", return_value=[[1.0] + [0.0] * 1535]):
        response = client.post(
            "/api/v4/ask",
            json={"question": "What is the capital of Mars?"},
        )

    assert response.status_code == 200
    data = response.get_json()
    # The IDK answer should fire because citations are weak (relevance < 0.5).
    assert data["answer"] == "I don't have anything in the workspace that answers this.", (
        f"Got fallback answer with weak citations: {data['answer'][:200]}"
    )
    assert data["confidence"] == "low"
    assert data["caveats"]
    assert any("matching" in c.lower() or "ground" in c.lower() for c in data["caveats"])


def test_ask_cache_hit(client, app):
    v4_ask._clear_cache()
    note = _create_entity(
        client,
        "note",
        "Mary's PR review feedback",
        "Mary said the PR review looked good.",
    )

    mock_result = [
        {
            "entity": note,
            "score": 0.95,
            "match": {
                "source": "semantic",
                "semantic_rank": 1,
                "snippet": "Mary said the PR review looked good.",
                "semantic_score": 0.95,
            },
        }
    ]

    with patch("services.v4_ask.search_entities") as mock_search, \
         patch("services.v4_ask._generate_answer") as mock_llm:
        mock_search.return_value = mock_result
        mock_llm.return_value = "Cached answer from LLM."
        response1 = client.post(
            "/api/v4/ask",
            json={"question": "cache hit test question"},
        )
        response2 = client.post(
            "/api/v4/ask",
            json={"question": "cache hit test question"},
        )

    assert response1.status_code == 200
    assert response2.status_code == 200
    data1 = response1.get_json()
    data2 = response2.get_json()
    assert data1 == data2
    assert data1["answer"] == "Cached answer from LLM."
    assert mock_llm.call_count == 1
