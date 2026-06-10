#!/usr/bin/env python3
"""Replay eval: score the extraction+reconciliation pipeline against labeled fixtures.

Reads tests/fixtures/replay/labels.json (hand-labeled expected decisions) and
tests/fixtures/replay/suggestions.json (source note content).

For each labeled suggestion whose source note has content, runs:
  1. extract_capture_candidates(source_note_content)
  2. reconcile_candidates(candidates)

Scores the pipeline decision against the label and prints a summary.
Results are written to docs/iterations/replay_results/<timestamp>.json.

Usage:
    python scripts/replay_eval.py [--dry-run]

    --dry-run: print what would run without calling the model (uses heuristic fallback)

Requires OPENAI_API_KEY in environment (or falls back to heuristics without it).
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "replay"
RESULTS_DIR = REPO_ROOT / "docs" / "iterations" / "replay_results"

# Add repo root to sys.path so we can import the services
sys.path.insert(0, str(REPO_ROOT))


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        print(f"ERROR: {path} not found. Run scripts/export_replay_fixtures.py first.", file=sys.stderr)
        sys.exit(1)


def setup_flask_context():
    """Push a Flask app context so DB models and services work."""
    os.environ.setdefault("DATABASE_URL", "postgresql://engram:engram@localhost:5432/engram")
    from app import create_app
    app = create_app("default")
    ctx = app.app_context()
    ctx.push()
    return ctx


def _normalize_action(decision):
    return (decision.get("action") or "new").lower()


def score_decision(label, decision, candidates):
    """Score one reconciliation decision against its label.

    Returns a dict with: correct (bool), label, got, reason.
    """
    expected = label.get("expected_action", "TODO")
    if expected == "TODO":
        return None  # not labeled yet

    got = _normalize_action(decision)
    expected_target = (label.get("expected_target_title") or "").strip().lower()
    got_target_id = decision.get("target_id")

    if expected in ("update", "link"):
        # Correct if the action matches AND a target was resolved.
        # "progress_update" also counts: it resolves to the same existing
        # entity, just routed through the activity-update mechanism instead
        # of a field update or bare link.
        correct = got in (expected, "update", "link", "progress_update") and got_target_id is not None
    elif expected == "new":
        correct = got == "new"
    elif expected == "accept":
        # For accepted suggestions: any non-"new" decision with a target is correct
        correct = got in ("update", "link", "progress_update") and got_target_id is not None
    else:
        correct = False

    return {
        "correct": correct,
        "expected": expected,
        "got": got,
        "got_target_id": got_target_id,
        "expected_target_title": expected_target,
        "reason": decision.get("reason", ""),
    }


def run_eval(labels, suggestions_by_id, dry_run=False):
    from services.v4_extraction import extract_capture_candidates, normalize_candidates
    from services.v4_reconciliation import reconcile_candidates

    results = []
    skipped = 0

    for label in labels:
        if label.get("expected_action") == "TODO":
            skipped += 1
            continue

        sid = label["suggestion_id"]
        sug = suggestions_by_id.get(sid)
        if not sug:
            print(f"  [skip] suggestion {sid} not found in suggestions.json")
            skipped += 1
            continue

        note_content = sug.get("source_note_content") or ""
        if not note_content.strip():
            print(f"  [skip] {label.get('suggested_title', sid)!r}: no source note content")
            skipped += 1
            continue

        print(f"  [eval] {label.get('suggested_title', '')!r} (expect: {label['expected_action']})")

        if dry_run:
            result = {
                "suggestion_id": sid,
                "suggested_title": label.get("suggested_title", ""),
                "expected_action": label["expected_action"],
                "dry_run": True,
                "score": None,
            }
            results.append(result)
            continue

        try:
            extraction = extract_capture_candidates(note_content)
            if not extraction:
                extraction = {}
            candidates = []
            for lc in extraction.get("links") or []:
                t = lc.get("target_type") or lc.get("type")
                if t:
                    candidates.append({**lc, "type": t, "_source": "link"})
            for ec in extraction.get("entities") or []:
                if ec.get("type"):
                    candidates.append({**ec, "_source": "entity"})

            if not candidates:
                result = {
                    "suggestion_id": sid,
                    "suggested_title": label.get("suggested_title", ""),
                    "expected_action": label["expected_action"],
                    "got_action": "no_candidates",
                    "correct": label["expected_action"] == "new",
                    "candidates_extracted": 0,
                    "reason": "extraction returned no candidates",
                }
                results.append(result)
                continue

            decisions = reconcile_candidates(candidates)

            # Find the decision that best matches the suggestion's titled entity
            expected_title = (label.get("suggested_title") or "").lower()
            best_decision = None
            best_candidate = None
            for c, d in zip(candidates, decisions):
                c_title = (c.get("title") or "").lower()
                if expected_title and c_title and expected_title in c_title or c_title in expected_title:
                    best_decision = d
                    best_candidate = c
                    break
            if best_decision is None and decisions:
                best_decision = decisions[0]
                best_candidate = candidates[0]

            score = score_decision(label, best_decision, candidates) if best_decision else None

            result = {
                "suggestion_id": sid,
                "suggested_title": label.get("suggested_title", ""),
                "source_note_title": sug.get("source_note_title", ""),
                "expected_action": label["expected_action"],
                "expected_target_title": label.get("expected_target_title", ""),
                "candidates_extracted": len(candidates),
                "matched_candidate_title": (best_candidate or {}).get("title", ""),
                "got_action": (best_decision or {}).get("action", "none"),
                "got_target_id": (best_decision or {}).get("target_id"),
                "got_reason": (best_decision or {}).get("reason", ""),
                "correct": (score or {}).get("correct", False),
                "label_notes": label.get("notes", ""),
            }
            results.append(result)

        except Exception as e:
            print(f"    ERROR: {e}", file=sys.stderr)
            results.append({
                "suggestion_id": sid,
                "suggested_title": label.get("suggested_title", ""),
                "expected_action": label["expected_action"],
                "error": str(e),
                "correct": False,
            })

    return results, skipped


def print_summary(results, skipped):
    labeled = [r for r in results if "correct" in r and not r.get("dry_run")]
    if not labeled:
        print("\nNo labeled results to score.")
        return

    correct = sum(1 for r in labeled if r["correct"])
    total = len(labeled)
    print(f"\n{'='*50}")
    print(f"Results: {correct}/{total} correct ({100*correct//total}%)")
    print(f"Skipped (unlabeled or no content): {skipped}")
    print(f"{'='*50}")

    wrong = [r for r in labeled if not r["correct"]]
    if wrong:
        print("\nIncorrect decisions:")
        for r in wrong:
            print(f"  [{r.get('got_action','?')} ≠ {r['expected_action']}] "
                  f"{r['suggested_title']!r}")
            if r.get("got_reason"):
                print(f"    reason: {r['got_reason']}")


def main():
    parser = argparse.ArgumentParser(description="Replay eval for reconciliation pipeline")
    parser.add_argument("--dry-run", action="store_true", help="List what would run without calling the model")
    args = parser.parse_args()

    labels = load_json(FIXTURES_DIR / "labels.json")
    suggestions = load_json(FIXTURES_DIR / "suggestions.json")
    suggestions_by_id = {s["id"]: s for s in suggestions}

    labeled_count = sum(1 for l in labels if l.get("expected_action") != "TODO")
    print(f"[eval] {len(labels)} labels loaded, {labeled_count} ready to evaluate")

    if labeled_count == 0:
        print("[eval] No labels yet. Edit tests/fixtures/replay/labels.json first.")
        sys.exit(0)

    if not args.dry_run:
        print("[eval] Setting up Flask app context...")
        setup_flask_context()

    results, skipped = run_eval(labels, suggestions_by_id, dry_run=args.dry_run)
    print_summary(results, skipped)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"{ts}.json"
    out_path.write_text(json.dumps({
        "timestamp": ts,
        "dry_run": args.dry_run,
        "total": len(results),
        "skipped": skipped,
        "correct": sum(1 for r in results if r.get("correct")),
        "results": results,
    }, indent=2, default=str))
    print(f"\n[eval] Results written to {out_path}")


if __name__ == "__main__":
    main()
