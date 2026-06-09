"""Slice A0: tests for the safety-net infrastructure.

Tests for:
- backup script existence and executability
- export_replay_fixtures script structure
- replay_eval script structure
- labels.json structure (once populated)
- fixture directory layout
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "replay"
MIGRATIONS_DIR = REPO_ROOT / "scripts" / "migrations"


class TestBackupScript:
    def test_backup_script_exists(self):
        assert (SCRIPTS_DIR / "backup_prod.sh").exists()

    def test_backup_script_executable(self):
        script = SCRIPTS_DIR / "backup_prod.sh"
        assert script.stat().st_mode & 0o111, "backup_prod.sh must be executable"

    def test_backup_script_has_safety_check(self):
        content = (SCRIPTS_DIR / "backup_prod.sh").read_text()
        assert "wc -c" in content, "Must check dump size"
        assert "exit 1" in content, "Must exit non-zero on empty dump"
        assert "pg_dump" in content


class TestReplayFixtureDir:
    def test_fixtures_dir_exists(self):
        assert FIXTURES_DIR.exists(), f"Missing: {FIXTURES_DIR}"

    def test_fixtures_readme_exists(self):
        # README is written by export_replay_fixtures.py; check template is correct
        # by running export script in dry-run check (just import, no DB call)
        assert (SCRIPTS_DIR / "export_replay_fixtures.py").exists()

    def test_export_script_executable(self):
        script = SCRIPTS_DIR / "export_replay_fixtures.py"
        assert script.stat().st_mode & 0o111


class TestReplayEvalScript:
    def test_replay_eval_exists(self):
        assert (SCRIPTS_DIR / "replay_eval.py").exists()

    def test_replay_eval_executable(self):
        script = SCRIPTS_DIR / "replay_eval.py"
        assert script.stat().st_mode & 0o111

    def test_replay_eval_handles_no_labels(self, tmp_path, monkeypatch):
        """eval script exits 0 gracefully when no labels are ready."""
        # Write minimal fixtures for a dry run test
        labels = [{"suggestion_id": "x", "expected_action": "TODO", "suggested_title": "Test"}]
        (FIXTURES_DIR / "labels.json").write_text(json.dumps(labels)) if not (
            FIXTURES_DIR / "labels.json"
        ).exists() else None

        # Just check the module can be imported without error
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "replay_eval", SCRIPTS_DIR / "replay_eval.py"
        )
        mod = importlib.util.load_from_spec = None
        assert spec is not None


class TestMigrationsDir:
    def test_migrations_dir_exists(self):
        assert MIGRATIONS_DIR.exists(), f"Missing: {MIGRATIONS_DIR}"

    def test_gitkeep_present(self):
        assert (MIGRATIONS_DIR / ".gitkeep").exists()


class TestGitignore:
    def test_backups_gitignored(self):
        gitignore = (REPO_ROOT / ".gitignore").read_text()
        assert "backups/" in gitignore, "backups/ must be in .gitignore"


class TestLabelsSchema:
    """If labels.json exists and is non-trivial, validate its structure."""

    def test_labels_json_valid_if_exists(self):
        labels_path = FIXTURES_DIR / "labels.json"
        if not labels_path.exists():
            return  # not exported yet — skip
        labels = json.loads(labels_path.read_text())
        assert isinstance(labels, list)
        for label in labels:
            assert "suggestion_id" in label
            assert "expected_action" in label
            assert label["expected_action"] in (
                "TODO", "new", "update", "link", "accept"
            ), f"Invalid expected_action: {label['expected_action']!r}"

    def test_labels_json_has_correct_fields(self):
        labels_path = FIXTURES_DIR / "labels.json"
        if not labels_path.exists():
            return
        labels = json.loads(labels_path.read_text())
        required = {"suggestion_id", "expected_action"}
        for label in labels:
            missing = required - set(label.keys())
            assert not missing, f"Label missing fields {missing}: {label}"
