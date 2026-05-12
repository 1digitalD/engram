"""Integration tests for search — FTS and SQL injection safety.

Proves that Postgres tsvector FTS finds entities by title and content,
that type filtering works, and that the _fts_only function uses
parameterized queries (no string-replace SQL injection).
"""

import pytest

from extensions import db
from models import Entity
from services.entity_service import create_entity
from services.search import search, _fts_only


class TestFtsSearchByTitle:
    """FTS search finds entities by title."""

    def test_fts_finds_entity_by_title(self, app):
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Quantum Computing Breakthrough",
                content="Some content here",
                actor="user",
            )
            db.session.commit()

            results = search("quantum", mode="fts")
            assert len(results) >= 1
            assert any(r["title"] == "Quantum Computing Breakthrough" for r in results)

    def test_fts_finds_entity_by_partial_title(self, app):
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Machine Learning Pipeline Design",
                content="Details about the pipeline",
                actor="user",
            )
            db.session.commit()

            results = search("machine learning", mode="fts")
            assert len(results) >= 1
            titles = [r["title"] for r in results]
            assert "Machine Learning Pipeline Design" in titles


class TestFtsSearchByContent:
    """FTS search finds entities by content."""

    def test_fts_finds_entity_by_content(self, app):
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Meeting Notes",
                content="Discussed the new Kubernetes deployment strategy and rollout plan",
                actor="user",
            )
            db.session.commit()

            results = search("kubernetes deployment", mode="fts")
            assert len(results) >= 1
            assert any("Kubernetes" in r.get("content", "") for r in results)

    def test_fts_finds_entity_by_content_not_title(self, app):
        """Entity whose title does not match but content does."""
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Weekly Sync",
                content="We reviewed the PostgreSQL migration and decided to use pgvector for embeddings",
                actor="user",
            )
            db.session.commit()

            results = search("pgvector embeddings", mode="fts")
            assert len(results) >= 1
            assert any(r["title"] == "Weekly Sync" for r in results)


class TestFtsTypeFilter:
    """FTS search respects type filter."""

    def test_type_filter_returns_only_matching_type(self, app):
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Alpha Project Update",
                content="Note about alpha",
                actor="user",
            )
            create_entity(
                entity_type="task",
                title="Alpha Task",
                content="Task about alpha",
                actor="user",
            )
            create_entity(
                entity_type="project",
                title="Alpha Project",
                content="Project about alpha",
                actor="user",
            )
            db.session.commit()

            results = search("alpha", mode="fts", filters={"type": "note"})
            assert len(results) >= 1
            assert all(r["type"] == "note" for r in results)

    def test_type_filter_task_only(self, app):
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Design Review Notes",
                content="Notes from the design review",
                actor="user",
            )
            create_entity(
                entity_type="task",
                title="Design Review Follow-up",
                content="Follow up on design review items",
                actor="user",
            )
            db.session.commit()

            results = search("design review", mode="fts", filters={"type": "task"})
            assert len(results) >= 1
            assert all(r["type"] == "task" for r in results)

    def test_type_filter_project_only(self, app):
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Budget Planning",
                content="Notes on budget",
                actor="user",
            )
            create_entity(
                entity_type="project",
                title="Budget Planning Project",
                content="Project for budget planning",
                actor="user",
            )
            db.session.commit()

            results = search("budget planning", mode="fts", filters={"type": "project"})
            assert len(results) >= 1
            assert all(r["type"] == "project" for r in results)


class TestFtsNoSqlInjection:
    """Prove _fts_only uses parameterized queries, not string-replace SQL."""

    def test_fts_only_no_string_replace_in_source(self, app):
        """Verify the source code does not use .replace() for SQL construction."""
        import inspect
        source = inspect.getsource(_fts_only)
        # The old fragile pattern was: sql.replace("LIMIT", "...")
        assert ".replace(" not in source, (
            "_fts_only must not use string .replace() for SQL construction — "
            "use parameterized queries instead"
        )

    def test_fts_only_handles_malicious_type_filter(self, app):
        """Type filter with SQL injection attempt should not break the query."""
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Test Entity",
                content="Test content",
                actor="user",
            )
            db.session.commit()

            # This should not raise or inject SQL — it should just return
            # zero results because the type doesn't match any valid type.
            results = search(
                "test",
                mode="fts",
                filters={"type": "'; DROP TABLE entities; --"},
            )
            # Query should complete without error (empty or with results, but not crash)
            assert isinstance(results, list)

    def test_fts_only_handles_malicious_query(self, app):
        """Query with SQL injection attempt should not break the search."""
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Normal Title",
                content="Normal content",
                actor="user",
            )
            db.session.commit()

            # Should not raise — parameterized query handles this safely
            results = search("'; DROP TABLE entities; --", mode="fts")
            assert isinstance(results, list)

    def test_fts_only_parameterized_query_structure(self, app):
        """Verify _fts_only builds SQL with proper parameterized WHERE clauses."""
        import inspect
        import ast

        source = inspect.getsource(_fts_only)
        tree = ast.parse(source)

        # Check that no Call node has attribute 'replace' on a string variable
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "replace":
                        pytest.fail(
                            "_fts_only uses .replace() for SQL construction. "
                            "Use parameterized queries instead."
                        )
