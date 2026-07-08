#!/usr/bin/env python3
"""Replay eval for reconciliation accuracy and report grouping quality."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "replay"
RESULTS_DIR = REPO_ROOT / "docs" / "iterations" / "replay_results"
SECTION_ORDER = [
    "routing_summary",
    "applied_annotations",
    "proposed_commitments",
    "decisions",
    "questions",
    "leftovers",
]
APPLIED_EVENT_KINDS = {"tag_added", "relationship_added", "ai_updated", "ai_processed"}

sys.path.insert(0, str(REPO_ROOT))


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        print(
            f"ERROR: {path} not found. Run scripts/export_replay_fixtures.py first.",
            file=sys.stderr,
        )
        sys.exit(1)


def setup_flask_context():
    """Push Flask app context so DB-backed services can run."""
    os.environ.setdefault("DATABASE_URL", "postgresql://engram:engram@localhost:5432/engram")
    from app import create_app

    app = create_app("default")
    ctx = app.app_context()
    ctx.push()
    return ctx


def _normalize_action(decision):
    return (decision or {}).get("action") or "none"


def score_decision(label, decision, candidates):
    """Score one reconciliation decision against its label."""
    expected = label.get("expected_action", "TODO")
    if expected == "TODO":
        return None

    got = _normalize_action(decision)
    expected_target = (label.get("expected_target_title") or "").strip().lower()
    got_target_id = (decision or {}).get("target_id")

    if expected in {"update", "link"}:
        correct = got in {expected, "update", "link", "progress_update"} and got_target_id is not None
    elif expected == "new":
        correct = got == "new"
    elif expected == "accept":
        correct = got in {"update", "link", "progress_update"} and got_target_id is not None
    else:
        correct = False

    return {
        "correct": correct,
        "expected": expected,
        "got": got,
        "got_target_id": got_target_id,
        "expected_target_title": expected_target,
        "reason": (decision or {}).get("reason", ""),
        "candidates_considered": len(candidates or []),
    }


def _extract_candidates(extraction):
    candidates = []
    for link_candidate in extraction.get("links") or []:
        candidate_type = link_candidate.get("target_type") or link_candidate.get("type")
        if candidate_type:
            candidates.append({**link_candidate, "type": candidate_type, "_source": "link"})
    for entity_candidate in extraction.get("entities") or []:
        if entity_candidate.get("type"):
            candidates.append({**entity_candidate, "_source": "entity"})
    return candidates


def _best_match_for_label(label, candidates, decisions):
    expected_title = (label.get("suggested_title") or "").strip().lower()
    for candidate, decision in zip(candidates, decisions):
        candidate_title = (candidate.get("title") or "").strip().lower()
        if not expected_title:
            break
        if candidate_title and (expected_title in candidate_title or candidate_title in expected_title):
            return candidate, decision
    if candidates and decisions:
        return candidates[0], decisions[0]
    return None, None


def run_eval(labels, suggestions_by_id, dry_run=False):
    from services.v4_extraction import extract_capture_candidates
    from services.v4_reconciliation import reconcile_candidates

    results = []
    skipped = 0

    for label in labels:
        if label.get("expected_action") == "TODO":
            skipped += 1
            continue

        suggestion_id = label["suggestion_id"]
        suggestion = suggestions_by_id.get(suggestion_id)
        if not suggestion:
            print(f"  [skip] suggestion {suggestion_id} not found in suggestions.json")
            skipped += 1
            continue

        note_content = suggestion.get("source_note_content") or ""
        if not note_content.strip():
            print(f"  [skip] {label.get('suggested_title', suggestion_id)!r}: no source note content")
            skipped += 1
            continue

        print(
            f"  [eval] {label.get('suggested_title', '')!r} "
            f"(expect: {label.get('expected_action', 'TODO')})"
        )

        if dry_run:
            results.append(
                {
                    "suggestion_id": suggestion_id,
                    "suggested_title": label.get("suggested_title", ""),
                    "expected_action": label.get("expected_action"),
                    "dry_run": True,
                }
            )
            continue

        try:
            extraction = extract_capture_candidates(note_content) or {}
            candidates = _extract_candidates(extraction)
            if not candidates:
                results.append(
                    {
                        "suggestion_id": suggestion_id,
                        "suggested_title": label.get("suggested_title", ""),
                        "source_note_title": suggestion.get("source_note_title", ""),
                        "expected_action": label.get("expected_action"),
                        "got_action": "no_candidates",
                        "correct": label.get("expected_action") == "new",
                        "candidates_extracted": 0,
                        "label_notes": label.get("notes", ""),
                    }
                )
                continue

            decisions = reconcile_candidates(candidates)
            best_candidate, best_decision = _best_match_for_label(label, candidates, decisions)
            score = score_decision(label, best_decision, candidates) if best_decision else None
            results.append(
                {
                    "suggestion_id": suggestion_id,
                    "suggested_title": label.get("suggested_title", ""),
                    "source_note_title": suggestion.get("source_note_title", ""),
                    "expected_action": label.get("expected_action"),
                    "expected_target_title": label.get("expected_target_title", ""),
                    "candidates_extracted": len(candidates),
                    "matched_candidate_title": (best_candidate or {}).get("title", ""),
                    "got_action": (best_decision or {}).get("action", "none"),
                    "got_target_id": (best_decision or {}).get("target_id"),
                    "got_reason": (best_decision or {}).get("reason", ""),
                    "correct": bool((score or {}).get("correct")),
                    "label_notes": label.get("notes", ""),
                }
            )
        except Exception as exc:  # pragma: no cover - surfaced in result payload
            print(f"  ERROR: {exc}", file=sys.stderr)
            results.append(
                {
                    "suggestion_id": suggestion_id,
                    "suggested_title": label.get("suggested_title", ""),
                    "expected_action": label.get("expected_action"),
                    "error": str(exc),
                    "correct": False,
                }
            )

    return results, skipped


def _item_payload(item):
    payload = item.get("payload") or {}
    return payload if isinstance(payload, dict) else {}


def _expected_section_for_item(item):
    kind = item.get("kind")
    payload = _item_payload(item)

    if kind == "routing_summary":
        return "routing_summary"
    if item.get("event_id") or kind in APPLIED_EVENT_KINDS:
        return "applied_annotations"
    if kind == "attribution" or (item.get("question") and item.get("owner") is None):
        return "questions"
    if kind == "create_decision" or payload.get("statement"):
        return "decisions"
    if payload.get("type") == "task":
        if payload.get("assigned_to") or item.get("owner"):
            return "proposed_commitments"
        return "questions"
    return "leftovers"


def score_report_grouping(report):
    """Score whether report items landed in the expected sections and order."""
    sections = report.get("sections") or []
    total_items = 0
    correctly_grouped = 0

    for section in sections:
        section_name = section.get("name")
        for item in section.get("items") or []:
            total_items += 1
            if _expected_section_for_item(item) == section_name:
                correctly_grouped += 1

    non_empty_sections = [s.get("name") for s in sections if s.get("items")]
    ordered_sections = sorted(non_empty_sections, key=lambda name: SECTION_ORDER.index(name))
    section_order_score = 1.0 if non_empty_sections == ordered_sections else 0.0
    grouping_score = round(correctly_grouped / total_items, 3) if total_items else 1.0
    overall_score = round((grouping_score + section_order_score) / 2, 3)

    return {
        "report_id": report.get("id"),
        "source_note_id": report.get("source_note_id"),
        "items_scored": total_items,
        "correctly_grouped": correctly_grouped,
        "grouping_score": grouping_score,
        "section_order_score": section_order_score,
        "overall_score": overall_score,
    }


def run_report_grouping_eval(notes, suggestions):
    from services.v4_report import build_report

    notes_by_id = {note["id"]: note for note in notes}
    suggestions_by_note = {}
    for suggestion in suggestions:
        note_id = suggestion.get("source_note_id")
        if note_id:
            suggestions_by_note.setdefault(note_id, []).append(suggestion)

    results = []
    for note_id, note_suggestions in suggestions_by_note.items():
        note = notes_by_id.get(note_id)
        if not note or not note_suggestions:
            continue
        report = build_report(note, [], note_suggestions)
        score = score_report_grouping(report)
        score["source_note_title"] = note.get("title", "")
        score["suggestion_count"] = len(note_suggestions)
        results.append(score)

    reports_scored = len(results)
    items_scored = sum(row["items_scored"] for row in results)
    correctly_grouped = sum(row["correctly_grouped"] for row in results)
    grouping_score = round(correctly_grouped / items_scored, 3) if items_scored else 1.0
    order_sum = sum(row["section_order_score"] for row in results)
    section_order_score = round(order_sum / reports_scored, 3) if reports_scored else 1.0
    overall_score = round((grouping_score + section_order_score) / 2, 3)

    return results, {
        "reports_scored": reports_scored,
        "items_scored": items_scored,
        "correctly_grouped": correctly_grouped,
        "grouping_score": grouping_score,
        "section_order_score": section_order_score,
        "overall_score": overall_score,
    }


def print_summary(results, skipped, report_grouping):
    labeled = [row for row in results if "correct" in row and not row.get("dry_run")]
    print(f"\n{'=' * 50}")
    if labeled:
        correct = sum(1 for row in labeled if row["correct"])
        total = len(labeled)
        print(f"Decision accuracy: {correct}/{total} correct ({100 * correct // total}%)")
    else:
        print("Decision accuracy: dry run only")
    print(f"Skipped (unlabeled or no content): {skipped}")
    print(
        "Report grouping: "
        f"{report_grouping['overall_score']:.3f} overall "
        f"(grouping {report_grouping['grouping_score']:.3f}, "
        f"sectioning {report_grouping['section_order_score']:.3f})"
    )
    print(f"{'=' * 50}")

    wrong = [row for row in labeled if not row["correct"]]
    if wrong:
        print("\nIncorrect decisions:")
        for row in wrong:
            print(f"  [{row.get('got_action', '?')} != {row['expected_action']}] {row['suggested_title']!r}")
            if row.get("got_reason"):
                print(f"      reason: {row['got_reason']}")


def main():
    parser = argparse.ArgumentParser(description="Replay eval for reconciliation and report grouping")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would run without calling model-backed reconciliation",
    )
    args = parser.parse_args()

    labels = load_json(FIXTURES_DIR / "labels.json")
    suggestions = load_json(FIXTURES_DIR / "suggestions.json")
    notes = load_json(FIXTURES_DIR / "notes.json")
    suggestions_by_id = {row["id"]: row for row in suggestions}
    labeled_count = sum(1 for row in labels if row.get("expected_action") != "TODO")

    print(f"[eval] {len(labels)} labels loaded, {labeled_count} ready to evaluate")
    if labeled_count == 0:
        print("[eval] No labels yet. Edit tests/fixtures/replay/labels.json first.")
        sys.exit(0)

    app_context = None
    if not args.dry_run:
        print("[eval] Setting up Flask app context...")
        app_context = setup_flask_context()

    try:
        results, skipped = run_eval(labels, suggestions_by_id, dry_run=args.dry_run)
        report_scores, report_grouping = run_report_grouping_eval(notes, suggestions)
        print_summary(results, skipped, report_grouping)
    finally:
        if app_context is not None:
            app_context.pop()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"{timestamp}.json"
    out_path.write_text(
        json.dumps(
            {
                "timestamp": timestamp,
                "dry_run": args.dry_run,
                "total": len(results),
                "skipped": skipped,
                "correct": sum(1 for row in results if row.get("correct")),
                "results": results,
                "report_grouping": report_grouping,
                "report_grouping_results": report_scores,
            },
            indent=2,
        )
    )
    print(f"\n[eval] Wrote {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
