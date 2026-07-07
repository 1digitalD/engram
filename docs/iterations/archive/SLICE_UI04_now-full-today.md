# SLICE_UI04 — Now full today payload

> **Task id:** `ui-04-now-full-today` | **Risk:** medium | **Status:** Pending

Extend `V5Now` to use blocked/waiting, follow-ups, recent_notes, pending_suggestions from `/api/v4/today`. See `prd.json` acceptance criteria.

```
cd ui && npm test -- V5Now
TEST_DATABASE_URL=...5433... ./venv/bin/pytest tests/integration/test_v4_today.py -q
```

**Acceptance met:** [ ] yes / [ ] no
