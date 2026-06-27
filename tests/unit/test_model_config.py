"""Pin v4 chat model defaults to gpt-5.4-nano and verify env-var overrides."""
from __future__ import annotations

import importlib
import os

import pytest

CHAT_MODEL_ENV_VARS = (
    "OPENAI_EXTRACTION_MODEL",
    "OPENAI_ACTIVITY_UPDATE_MODEL",
    "OPENAI_RECONCILIATION_MODEL",
    "OPENAI_SUMMARIZATION_MODEL",
    "OPENAI_BRIEF_MODEL",
)

SERVICE_MODULES = (
    "services.v4_extraction",
    "services.v4_reconciliation",
    "services.v4_summarization",
    "services.v4_brief",
)


def _clear_chat_model_env(monkeypatch):
    """Unset all chat-model env vars so defaults are exercised."""
    for var in CHAT_MODEL_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def _reload_services():
    """Reload llm_models and the services that consume it."""
    import services.llm_models as llm_models

    importlib.reload(llm_models)
    for name in SERVICE_MODULES:
        importlib.reload(importlib.import_module(name))


def test_chat_model_defaults_to_gpt_5_4_nano(monkeypatch):
    _clear_chat_model_env(monkeypatch)
    _reload_services()

    from services import v4_extraction, v4_reconciliation, v4_summarization, v4_brief

    assert v4_extraction.EXTRACTION_MODEL == "gpt-5.4-nano"
    assert v4_extraction.ACTIVITY_UPDATE_EXTRACTION_MODEL == "gpt-5.4-nano"
    assert v4_reconciliation.RECONCILIATION_MODEL == "gpt-5.4-nano"
    assert v4_summarization.SUMMARIZATION_MODEL == "gpt-5.4-nano"
    assert v4_brief.BRIEF_MODEL == "gpt-5.4-nano"


def test_chat_model_env_overrides_win(monkeypatch):
    overrides = {
        "OPENAI_EXTRACTION_MODEL": "o3-mini",
        "OPENAI_ACTIVITY_UPDATE_MODEL": "o3-mini",
        "OPENAI_RECONCILIATION_MODEL": "gpt-4o",
        "OPENAI_SUMMARIZATION_MODEL": "gpt-4o",
        "OPENAI_BRIEF_MODEL": "o1",
    }
    for var, value in overrides.items():
        monkeypatch.setenv(var, value)
    _reload_services()

    from services import v4_extraction, v4_reconciliation, v4_summarization, v4_brief

    assert v4_extraction.EXTRACTION_MODEL == overrides["OPENAI_EXTRACTION_MODEL"]
    assert v4_extraction.ACTIVITY_UPDATE_EXTRACTION_MODEL == overrides["OPENAI_ACTIVITY_UPDATE_MODEL"]
    assert v4_reconciliation.RECONCILIATION_MODEL == overrides["OPENAI_RECONCILIATION_MODEL"]
    assert v4_summarization.SUMMARIZATION_MODEL == overrides["OPENAI_SUMMARIZATION_MODEL"]
    assert v4_brief.BRIEF_MODEL == overrides["OPENAI_BRIEF_MODEL"]


def test_resolve_chat_model_uses_default_when_env_unset(monkeypatch):
    monkeypatch.delenv("OPENAI_FAKE_MODEL", raising=False)
    from services.llm_models import resolve_chat_model

    assert resolve_chat_model("OPENAI_FAKE_MODEL") == "gpt-5.4-nano"
    assert resolve_chat_model("OPENAI_FAKE_MODEL", default="custom-default") == "custom-default"


def test_resolve_chat_model_prefers_non_empty_env(monkeypatch):
    monkeypatch.setenv("OPENAI_FAKE_MODEL", "env-model")
    from services.llm_models import resolve_chat_model

    assert resolve_chat_model("OPENAI_FAKE_MODEL") == "env-model"


def test_resolve_chat_model_falls_back_when_env_is_empty(monkeypatch):
    monkeypatch.setenv("OPENAI_FAKE_MODEL", "")
    from services.llm_models import resolve_chat_model

    assert resolve_chat_model("OPENAI_FAKE_MODEL") == "gpt-5.4-nano"


def test_embedding_model_unchanged():
    from services.embeddings import EMBEDDING_MODEL

    assert EMBEDDING_MODEL == "text-embedding-3-small"
