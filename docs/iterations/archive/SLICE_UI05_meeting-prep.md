# SLICE_UI05 — Meeting prep + current load

> **Task id:** `ui-05-meeting-prep` | **Risk:** low | **Status:** Pending

Render `meeting_prep` and `current_load` on person detail. See `v5ThreadDetailUtils.js`.

```
cd ui && npm test -- V5ThreadDetail
TEST_DATABASE_URL=...5433... ./venv/bin/pytest tests/integration/test_v4_today.py -q -k meeting_prep
```

**Acceptance met:** [ ] yes / [ ] no
