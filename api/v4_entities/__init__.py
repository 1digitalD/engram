"""Compatibility shim for the former api/v4_entities.py module.

All implementation has moved into the api.v4 package. This module re-exports
the shared helpers so existing imports from api.v4_entities continue to work
without modifying callers or tests.
"""

from api.v4._shared import *  # noqa: F401,F403
