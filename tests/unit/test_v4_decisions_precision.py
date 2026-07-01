"""Precision test for decision extraction against a labeled corpus.

Mocks the OpenAI client so the test is deterministic and offline.
"""
import json
import os
import pathlib
from unittest.mock import MagicMock, patch

import pytest

from services.v4_decisions import extract_decisions_from_note


CORPUS_PATH = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "decisions_corpus.json"


class _MockMessage:
    def __init__(self, content):
        self.content = content


class _MockChoice:
    def __init__(self, content):
        self.message = _MockMessage(content)


class _MockCompletion:
    def __init__(self, content):
        self.choices = [_MockChoice(content)]


def _load_corpus():
    with open(CORPUS_PATH) as f:
        return json.load(f)["examples"]


def _client_for_example(example):
    client = MagicMock()
    client.chat.completions.create.return_value = _MockCompletion(
        json.dumps(example["mock"])
    )
    return client


def test_decision_extraction_precision_on_labeled_corpus(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ENGRAM_ALLOW_TEST_AI", "1")
    corpus = _load_corpus()
    true_positives = 0
    false_positives = 0
    false_negatives = 0

    for example in corpus:
        client = _client_for_example(example)
        with patch("services.v4_decisions.get_openai_client", return_value=client):
            decisions = extract_decisions_from_note(example["content"])

        predicted = len(decisions) > 0
        actual = example["label"] == "decision"

        if predicted and actual:
            true_positives += 1
        elif predicted and not actual:
            false_positives += 1
        elif not predicted and actual:
            false_negatives += 1

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) else 0

    assert precision >= 0.85, f"precision {precision:.2f} below 0.85 (TP={true_positives}, FP={false_positives}, FN={false_negatives})"
    assert recall >= 0.85, f"recall {recall:.2f} below 0.85 (TP={true_positives}, FP={false_positives}, FN={false_negatives})"
