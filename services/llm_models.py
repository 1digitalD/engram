"""Centralized chat model resolution for v4 LLM services.

This module exports a single helper used by all chat-completion services so
that the default model stays consistent and env-var overrides keep working.
Embeddings are intentionally NOT handled here; see services.embeddings.
"""
from __future__ import annotations

import os


def resolve_chat_model(env_var: str, default: str = "gpt-5.4-nano") -> str:
    """Return the model name to use for a chat-completion service.

    Reads the named environment variable. If unset or empty, falls back to
    ``default`` (canonical v4 default: gpt-5.4-nano).
    """
    return os.getenv(env_var, default) or default
