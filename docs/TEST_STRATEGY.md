# Engram v2 — Test Strategy
> TDD approach. Tests are written before implementation. A task is not done until its tests pass.

---

## Philosophy

1. **Tests before implementation.** Each agent writes the test file first, confirms it fails for the right reason, then implements.
2. **Tests are the contract.** If the spec and the test disagree, fix the test first, then align implementation.
3. **No mocking the database.** All integration tests run against a real Postgres test DB. Mocks are only for external APIs (OpenAI, Anthropic).
4. **Fast feedback.** Unit tests run in < 5s. Full suite runs in < 60s.
5. **Coverage gates.** Critical paths require ≥ 80% line coverage. Non-critical paths (MCP, summaries, daily notes) are exempt.

---

## Test Levels

```
tests/
├── conftest.py              ← fixtures, DB setup, factories, API mocks
├── unit/                    ← pure logic, no DB, no HTTP
│   ├── test_lifecycle.py    ← status transition validation
│   ├── test_ai_pipeline.py  ← extraction parsing, confidence thresholds
│   └── test_search.py       ← RRF fusion logic
├── integration/             ← real Postgres, real Flask test client
│   ├── test_entities.py     ← CRUD for all entity types
│   ├── test_links.py        ← entity_links create/delete/cascade
│   ├── test_events.py       ← entity_events audit log
│   ├── test_jobs.py         ← job queue enqueue/poll/retry
│   ├── test_ingestion.py    ← full ingest pipeline (OpenAI mocked)
│   └── test_search_api.py   ← search endpoint (embeddings mocked)
└── e2e/                     ← full stack, skipped in CI by default
    └── test_capture_flow.py
```

---

## Setup

### Test database

```bash
# Create test DB (run once)
createdb engram_test
psql engram_test -f docs/SCHEMA.sql
```

```bash
# .env.test (loaded by conftest.py)
DATABASE_URL=postgresql://localhost/engram_test
OPENAI_API_KEY=test-key-not-real
ANTHROPIC_API_KEY=test-key-not-real
```

### Running tests

```bash
# All tests
pytest -q

# Unit tests only (fastest)
pytest tests/unit/ -q

# Integration only
pytest tests/integration/ -q

# Single file
pytest tests/integration/test_entities.py -v

# With coverage report
pytest --cov=. --cov-report=term-missing --cov-config=.coveragerc -q

# Watch mode (install pytest-watch)
ptw tests/unit/ tests/integration/
```

### Coverage config (`.coveragerc`)
```ini
[run]
omit =
    .venv/*
    tests/*
    migrations/*
    scripts/*
    mcp_server/*

[report]
fail_under = 80
include =
    services/*
    api/*
    models.py
```

---

## conftest.py — Core Fixtures

Agents must not modify conftest.py without coordinating with others.

```python
# tests/conftest.py
import pytest
from unittest.mock import patch, MagicMock
from app import create_app
from extensions import db as _db
from sqlalchemy import text

@pytest.fixture(scope="session")
def app():
    app = create_app(testing=True)
    yield app

@pytest.fixture(scope="session")
def db(app):
    with app.app_context():
        yield _db

@pytest.fixture(autouse=True)
def reset_db(db):
    """Truncate all tables before each test."""
    with db.engine.connect() as conn:
        conn.execute(text("SELECT truncate_all_tables()"))
        conn.commit()

@pytest.fixture
def client(app):
    return app.test_client()

# ── Entity factory ────────────────────────────────────────────────────────────

@pytest.fixture
def make_entity(db, app):
    """Factory for creating test entities directly in DB."""
    created = []
    def factory(type="note", title="Test", content="Test content",
                status="active", properties=None, **kwargs):
        from services.entity_service import create_entity
        with app.app_context():
            entity = create_entity(
                type=type, title=title, content=content,
                status=status, properties=properties or {},
                source="test", actor="user", **kwargs
            )
            created.append(entity.id)
            return entity
    yield factory

# ── OpenAI mock ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_openai():
    """Mock OpenAI API — returns deterministic extraction result."""
    from services.extractor import ExtractionResult
    result = ExtractionResult(
        summary="Test note summary",
        para_bucket="PROJECTS",
        confidence=0.95,
        suggested_project="Test Project",
        suggested_area=None,
        tasks=[],
        people=[],
        tags=["test"],
        reasoning="High confidence project note",
    )
    with patch("services.extractor._get_client") as mock:
        mock_response = MagicMock()
        mock_response.choices[0].message.parsed = result
        mock.return_value.beta.chat.completions.parse.return_value = mock_response
        yield result

@pytest.fixture
def mock_embed():
    """Mock OpenAI embeddings — returns zero vector."""
    import numpy as np
    with patch("services.embeddings.get_embedding") as mock:
        mock.return_value = [0.0] * 1536
        yield mock
```

---

## Test Patterns

### Unit test — lifecycle validation
```python
# tests/unit/test_lifecycle.py
from services.entity_service import VALID_TRANSITIONS, validate_transition

def test_task_pending_to_in_progress():
    validate_transition("task", "pending", "in_progress")  # must not raise

def test_task_done_to_archived_rejected():
    with pytest.raises(ValueError, match="invalid transition"):
        validate_transition("task", "done", "archived")

def test_project_completed_is_terminal_to_cancelled():
    with pytest.raises(ValueError, match="invalid transition"):
        validate_transition("project", "completed", "cancelled")

def test_note_only_has_active_and_archived():
    validate_transition("note", "active", "archived")
    with pytest.raises(ValueError):
        validate_transition("note", "active", "done")
```

### Integration test — entity CRUD
```python
# tests/integration/test_entities.py
def test_create_note_returns_immediately(client, mock_openai, mock_embed):
    """Note creation must return in < 200ms — AI is async."""
    import time
    start = time.time()
    resp = client.post("/api/v1/notes", json={"content": "quick capture"})
    elapsed = time.time() - start
    assert resp.status_code == 201
    assert elapsed < 0.2
    data = resp.get_json()["data"]
    assert data["ai_status"] == "pending"   # not yet classified

def test_status_transition_invalid_returns_400(client, make_entity):
    task = make_entity(type="task", status="done")
    resp = client.patch(f"/api/v1/tasks/{task.id}/status",
                        json={"status": "archived"})
    assert resp.status_code == 400
    assert "invalid transition" in resp.get_json()["error"]

def test_delete_note_without_cascade_returns_preview(client, make_entity):
    note = make_entity(type="note")
    task = make_entity(type="task")
    # link task to note (derived_from)
    client.post("/api/v1/entity-links", json={
        "src_id": task.id, "dst_id": note.id, "link_type": "derived_from"
    })
    resp = client.delete(f"/api/v1/notes/{note.id}?cascade=false")
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["safe_to_cascade"]) == 1   # task has no other links
    assert body["safe_to_cascade"][0]["id"] == task.id
```

### Integration test — AI event logging
```python
# tests/integration/test_events.py
def test_ai_classify_writes_entity_event(client, make_entity, mock_openai, mock_embed):
    from services.job_worker import process_job
    from models import Job
    note = make_entity(type="note", content="meeting with Sarah about Engram launch")
    # Run classify job synchronously for test
    job = Job.query.filter_by(entity_id=note.id, job_type="classify").first()
    process_job(job)
    resp = client.get(f"/api/v1/entities/{note.id}/events")
    events = resp.get_json()["data"]
    ai_event = next(e for e in events if e["event_type"] == "ai_classified")
    assert ai_event["actor"] == "agent:classify"
    assert ai_event["confidence"] == 0.95
    assert ai_event["new_value"]["para_bucket"] == "PROJECTS"

def test_status_change_writes_entity_event(client, make_entity):
    task = make_entity(type="task", status="pending")
    client.patch(f"/api/v1/tasks/{task.id}/status",
                 json={"status": "in_progress", "reason": "starting now"})
    resp = client.get(f"/api/v1/entities/{task.id}/events")
    events = resp.get_json()["data"]
    ev = next(e for e in events if e["event_type"] == "status_changed")
    assert ev["actor"] == "user"
    assert ev["old_value"]["status"] == "pending"
    assert ev["new_value"]["status"] == "in_progress"
    assert ev["reason"] == "starting now"
```

### Integration test — job worker
```python
# tests/integration/test_jobs.py
def test_failed_job_retries_with_backoff(app, make_entity, mock_embed):
    from services.job_worker import process_job
    from models import Job
    import datetime

    note = make_entity(type="note")
    job = Job.query.filter_by(entity_id=note.id, job_type="classify").first()

    with patch("services.ai_pipeline.run_classify", side_effect=Exception("API down")):
        process_job(job)

    job = Job.query.get(job.id)
    assert job.status == "failed"
    assert job.attempts == 1
    assert job.run_after > datetime.datetime.utcnow()  # backoff applied

def test_job_not_retried_after_max_attempts(app, make_entity):
    from models import Job
    note = make_entity(type="note")
    job = Job.query.filter_by(entity_id=note.id, job_type="classify").first()
    job.attempts = 3   # max
    # worker should skip this job
    from services.job_worker import get_next_job
    assert get_next_job() != job
```

---

## CI Configuration (`.github/workflows/test.yml`)

```yaml
name: Test
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: engram
          POSTGRES_PASSWORD: engram
          POSTGRES_DB: engram_test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Apply schema
        run: psql $DATABASE_URL -f docs/SCHEMA.sql
        env:
          DATABASE_URL: postgresql://engram:engram@localhost:5432/engram_test

      - name: Run tests
        run: pytest -q --cov=. --cov-report=term-missing
        env:
          DATABASE_URL: postgresql://engram:engram@localhost:5432/engram_test
          OPENAI_API_KEY: test-not-real
          ANTHROPIC_API_KEY: test-not-real
```

---

## What "Done" Means for Each Task

Every task in the agent plan is done when:
1. Its tests pass (`pytest tests/<relevant_file> -v` all green)
2. The full suite still passes (no regressions: `pytest -q`)
3. Coverage for the changed files is ≥ 80% (`pytest --cov=<file>`)
4. No mypy errors on changed files: `mypy <file> --ignore-missing-imports`

Agents must report: test output, coverage %, and any skipped/xfailed tests with reason.
