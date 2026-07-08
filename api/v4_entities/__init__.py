"""Compatibility shim for the former api/v4_entities.py module.

All implementation lives in ``api.v4._shared`` and domain route modules under
``api/v4/``. This package re-exports shared helpers so existing imports and
**test mocks** (``patch("api.v4_entities.<name>")``) continue to work.

Route modules that call shimmed helpers (e.g. ``capture._v4e._run_basic_capture_extraction``)
must use ``from api import v4_entities as _v4e`` — not direct ``_shared`` calls —
so integration tests can patch at the stable ``api.v4_entities`` path.
"""

from api.v4._shared import *  # noqa: F401,F403
