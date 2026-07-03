"""Golden-set eval harness for capture extraction quality (SQ-03).

This is a *decision tool*, not a CI gate: it calls the live OpenAI API and
scores real model output against a hand-labeled fixture set, so results can
shift between runs and between model/prompt changes. It is skipped by
default — see tests/eval/README.md for how to run it and add fixtures.

Design:
- `forbid_create` / `forbid_decision` / `expect_no_entities` are precision
  checks. Any match is a real regression (noise the user has to dismiss), so
  the test asserts on these — a violation fails the test.
- `must_create` / `target_status*` / `follow_up_expected` are recall checks.
  Real LLM output is not perfectly reproducible, so misses are reported in
  the printed table (and count against the aggregate recall score) but do
  not fail the test by themselves.
"""
import os

import pytest

from extensions import db
from models import Entity

from fixtures import FIXTURES, score_fixture

pytestmark = pytest.mark.skipif(
    os.getenv("ENGRAM_ALLOW_TEST_AI") != "1",
    reason=(
        "Golden capture eval calls live OpenAI and costs money. "
        "Set ENGRAM_ALLOW_TEST_AI=1 to run (see tests/eval/README.md)."
    ),
)

_RESULTS = []


def _seed_thread(client, spec):
    """Create the pre-existing entity a fixture wants seeded, if any."""
    if spec is None:
        return None
    payload = {"type": spec["type"], "title": spec["title"]}
    if spec.get("status"):
        payload["status"] = spec["status"]
    if spec.get("content"):
        payload["content"] = spec["content"]
    response = client.post("/api/v4/entities", json=payload)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def _refresh_status_and_follow_up(app, entity_id):
    if entity_id is None:
        return None, None
    with app.app_context():
        entity = db.session.get(Entity, entity_id)
        if entity is None:
            return None, None
        return entity.status, entity.follow_up_at


def _status_proposed_in_suggestions(data, wanted):
    for suggestion in data.get("suggestions") or []:
        fields = (suggestion.get("payload") or {}).get("fields") or {}
        if fields.get("status") in wanted:
            return True
    return False


def _follow_up_proposed_in_suggestions(data):
    for suggestion in data.get("suggestions") or []:
        fields = (suggestion.get("payload") or {}).get("fields") or {}
        if fields.get("follow_up_at"):
            return True
    return False


def _format_result_line(fixture_id, result, extra_notes):
    hits = len(result["hits"])
    total_required = hits + len(result["misses"])
    recall = f"{hits}/{total_required}" if total_required else "n/a"
    precision = "FAIL" if result["violations"] else "ok"
    notes = " ".join(n for n in extra_notes if n)
    return (
        f"{fixture_id:<38} recall={recall:<6} precision={precision:<5} "
        f"creates={len(result['creates'])}  {notes}"
    )


@pytest.fixture(scope="module", autouse=True)
def _print_aggregate_table():
    """Print a per-fixture table as tests run, then an aggregate summary.

    Only executes when the module actually ran (i.e. ENGRAM_ALLOW_TEST_AI=1) —
    module-scoped fixtures never set up for a module skipped at collection.
    """
    print("\n\n=== Golden capture eval — SQ-03 ===")
    print(f"{'fixture':<38} {'recall':<13} {'precision':<12} creates  notes")
    yield
    if not _RESULTS:
        return
    total_hits = sum(len(r["hits"]) for r in _RESULTS)
    total_required = total_hits + sum(len(r["misses"]) for r in _RESULTS)
    total_violations = sum(len(r["violations"]) for r in _RESULTS)
    clean_fixtures = sum(1 for r in _RESULTS if not r["violations"])
    n = len(_RESULTS)
    recall_pct = (total_hits / total_required * 100) if total_required else 0.0
    print("\n=== Aggregate ===")
    print(f"fixtures run: {n}")
    print(f"recall: {total_hits}/{total_required} required entities present ({recall_pct:.0f}%)")
    print(f"precision: {clean_fixtures}/{n} fixtures with zero forbidden outcomes")
    if total_violations:
        print(f"total forbidden-outcome violations: {total_violations}")
    print("=" * 60)


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f["id"] for f in FIXTURES])
def test_capture_golden(client, app, fixture):
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set — golden eval needs a live key")

    thread_spec = fixture.get("attached_thread")
    thread = _seed_thread(client, thread_spec)
    attach_as_thread = (thread_spec or {}).get("attach_as_thread", True)

    capture_payload = {"content": fixture["content"], "source": "eval", "mode": "auto"}
    if thread is not None and attach_as_thread:
        capture_payload["thread_id"] = thread["id"]

    response = client.post("/api/v4/capture", json=capture_payload)
    assert response.status_code == 201, response.get_json()
    data = response.get_json()

    expected = fixture["expected"]
    result = score_fixture(data, expected)

    notes = []
    if thread is not None and (expected.get("target_status") or expected.get("target_status_options")):
        wanted = expected.get("target_status_options") or [expected.get("target_status")]
        status, _follow_up = _refresh_status_and_follow_up(app, thread["id"])
        ok = status in wanted or _status_proposed_in_suggestions(data, wanted)
        notes.append(f"status:{'ok' if ok else 'MISS'}({status})")

    if expected.get("follow_up_expected"):
        follow_up_at = None
        if thread is not None:
            _status, follow_up_at = _refresh_status_and_follow_up(app, thread["id"])
        ok = bool(follow_up_at) or _follow_up_proposed_in_suggestions(data)
        notes.append(f"follow_up:{'ok' if ok else 'MISS'}")

    _RESULTS.append(result)
    print(_format_result_line(fixture["id"], result, notes))
    for miss in result["misses"]:
        print(f"    recall miss: expected {miss['want']}")

    assert not result["violations"], (
        f"fixture {fixture['id']!r} ({fixture['kind']}) produced forbidden outcome(s):\n"
        + "\n".join(f"  - {v['reason']} -> {v['match']}" for v in result["violations"])
    )
