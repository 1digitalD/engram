"""Unit tests for receipt-grounded nudge drafting (TC-44)."""

import json
import pathlib
from unittest.mock import MagicMock, patch

import pytest

from services import v4_nudge_draft as nudge_service


CORPUS_PATH = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "nudge_draft_corpus.json"


class _MockMessage:
    def __init__(self, content):
        self.content = content


class _MockChoice:
    def __init__(self, content):
        self.message = _MockMessage(content)


class _MockCompletion:
    def __init__(self, content):
        self.choices = [_MockChoice(content)]


def _client_for_example(example):
    client = MagicMock()
    client.chat.completions.create.return_value = _MockCompletion(
        json.dumps(example["mock"])
    )
    return client


def test_build_user_prompt_includes_original_ask_date_and_receipts():
    context = {
        "original_ask": "Send deck to Maria",
        "committed_at": "2026-06-28",
        "owner": {"title": "Maria"},
        "due_at": "2026-07-11T12:00:00Z",
        "source_note": {"quote": "Maria will send the deck by Friday."},
        "receipts": [
            {"label": "original ask", "value": "Send deck to Maria"},
            {"label": "committed date", "value": "2026-06-28"},
            {"label": "source note", "value": "Maria will send the deck by Friday."},
        ],
    }

    prompt = nudge_service.build_user_prompt(context)

    assert "Original ask: Send deck to Maria" in prompt
    assert "Committed date: 2026-06-28" in prompt
    assert "Receipts:" in prompt
    assert "original ask: Send deck to Maria" in prompt
    assert "committed date: 2026-06-28" in prompt
    assert "source note: Maria will send the deck by Friday." in prompt


def test_heuristic_draft_cites_original_ask_and_date():
    context = {
        "original_ask": "Complete security questionnaire",
        "committed_at": "2026-06-28",
        "owner": {"title": "Sam"},
        "source_note": {"quote": "Sam will complete the security questionnaire by end of June."},
        "receipts": [],
    }

    draft = nudge_service._heuristic_draft(context)

    assert "security questionnaire" in draft
    assert "28" in draft
    assert "Sam" in draft


def test_nudge_draft_corpus_prompt_fixtures(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ENGRAM_ALLOW_TEST_AI", "1")

    with open(CORPUS_PATH) as handle:
        corpus = json.load(handle)["examples"]

    for example in corpus:
        client = _client_for_example(example)
        with patch("services.v4_nudge_draft.get_openai_client", return_value=client):
            draft = nudge_service._generate_draft_text(example["context"])

        call = client.chat.completions.create.call_args
        user_prompt = call.kwargs["messages"][1]["content"]
        assert example["context"]["original_ask"] in user_prompt
        assert example["context"]["committed_at"] in user_prompt
        for receipt in example["context"]["receipts"]:
            assert receipt["value"] in user_prompt

        lowered = draft.lower()
        for needle in example["must_include"]:
            assert needle.lower() in lowered, f"{example['id']} missing {needle!r} in {draft!r}"


def test_gather_commitment_context_builds_receipts_from_task_links(app):
    from extensions import db
    from models import Entity, EntityLink

    with app.app_context():
        task = Entity(
            type="task",
            title="Legal read on clause 7",
            status="waiting",
            lifecycle="active",
            source="user",
            properties={},
            ai_meta={},
            ai_status="pending",
        )
        owner = Entity(
            type="person",
            title="Dana",
            status="active",
            lifecycle="active",
            source="user",
            properties={},
            ai_meta={},
            ai_status="pending",
        )
        note = Entity(
            type="note",
            title="Meeting notes",
            content="Dana committed to a legal read on clause 7 by Friday.",
            status="active",
            lifecycle="active",
            source="capture",
            properties={},
            ai_meta={},
            ai_status="pending",
        )
        db.session.add_all([task, owner, note])
        db.session.flush()

        db.session.add(
            EntityLink(
                source_entity_id=task.id,
                target_entity_id=owner.id,
                relationship_type="assigned_to",
            )
        )
        db.session.add(
            EntityLink(
                source_entity_id=task.id,
                target_entity_id=note.id,
                relationship_type="derived_from",
            )
        )
        db.session.commit()

        context = nudge_service.gather_commitment_context(task.id)

    assert context["original_ask"] == "Legal read on clause 7"
    assert context["committed_at"] is not None
    assert any(r["label"] == "original ask" for r in context["receipts"])
    assert any(r["label"] == "committed date" for r in context["receipts"])
    assert any(r["label"] == "source note" for r in context["receipts"])
    assert context["owner"]["title"] == "Dana"
