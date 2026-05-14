"""Shared utility functions used across the API and services."""

import os
import logging

logger = logging.getLogger(__name__)

VALID_PRIORITIES = {"low", "medium", "high", "urgent"}

_openai_client = None


def get_openai_client():
    """Lazy-init shared OpenAI client. Raises RuntimeError if key is missing."""
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set")
        _openai_client = OpenAI(api_key=key)
    return _openai_client


def parse_priority(val) -> str:
    """Normalize a priority value to a lowercase string. Defaults to 'medium'."""
    if val is None:
        return "medium"
    normalized = str(val).lower()
    return normalized if normalized in VALID_PRIORITIES else "medium"
