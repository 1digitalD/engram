#!/usr/bin/env bash
# Loopsmith recovery helper for the engram repo.
# Codifies the manual recovery steps from the loopsmith-control-plane skill.
# Idempotent; safe to re-run.
#
# Usage: bash scripts/loopsmith_recover.sh <repo-path> <action> [args...]
#
# Actions:
#   inspect              — read-only state snapshot
#   clean-all            — archive stale runs + reset state
#   archive-stale        — just archive .codloop/runs/*.json
#   reset-state          — just reset .codloop/state.json activeAttemptId
#   cherry-pick <worktree> <commit> — cherry-pick a worktree commit onto main

set -euo pipefail

REPO="${1:-}"
ACTION="${2:-}"

if [ -z "$REPO" ] || [ -z "$ACTION" ]; then
  echo "Usage: $0 <repo-path> <action> [args...]" >&2
  echo "  inspect" >&2
  echo "  clean-all" >&2
  echo "  archive-stale" >&2
  echo "  reset-state" >&2
  echo "  cherry-pick <worktree-path> <commit-sha>" >&2
  exit 1
fi

cd "$REPO"
CODLOOP="$REPO/.codloop"
RUNS_DIR="$CODLOOP/runs"
STATE_FILE="$CODLOOP/state.json"
ARCHIVE_DIR="$CODLOOP/runs/.archive-$(date -u +%Y%m%d-%H%M%S)"

case "$ACTION" in
  inspect)
    echo "=== State ==="
    if [ -f "$STATE_FILE" ]; then
      cat "$STATE_FILE"
    else
      echo "(no state.json)"
    fi
    echo ""
    echo "=== Run files (newest first) ==="
    if [ -d "$RUNS_DIR" ]; then
      ls -lt "$RUNS_DIR" | head -20
    else
      echo "(no runs dir)"
    fi
    echo ""
    echo "=== Open worktrees ==="
    git worktree list
    ;;

  archive-stale)
    if [ ! -d "$RUNS_DIR" ]; then
      echo "No runs dir to archive."
      exit 0
    fi
    mkdir -p "$ARCHIVE_DIR"
    # Archive any run JSON not in a sub-archive directory
    find "$RUNS_DIR" -maxdepth 1 -name "*.json" -type f -exec mv {} "$ARCHIVE_DIR/" \;
    echo "Archived run files to $ARCHIVE_DIR"
    ls "$ARCHIVE_DIR" | wc -l
    ;;

  reset-state)
    if [ ! -f "$STATE_FILE" ]; then
      echo "No state file to reset."
      exit 0
    fi
    python3 - <<PY
import json
from pathlib import Path
p = Path("$STATE_FILE")
data = json.loads(p.read_text())
data["activeAttemptId"] = None
data["updatedAt"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
p.write_text(json.dumps(data, indent=2))
print("activeAttemptId cleared.")
PY
    ;;

  clean-all)
    "$0" "$REPO" archive-stale
    "$0" "$REPO" reset-state
    echo ""
    echo "Next host-run-async will spawn fresh attempts."
    ;;

  cherry-pick)
    WORKTREE="${3:-}"
    COMMIT="${4:-}"
    if [ -z "$WORKTREE" ] || [ -z "$COMMIT" ]; then
      echo "Usage: $0 <repo> cherry-pick <worktree-path> <commit-sha>" >&2
      exit 1
    fi
    # Make sure main is up to date first
    git fetch "$WORKTREE" "$COMMIT" 2>/dev/null || true
    git -C "$REPO" cherry-pick "$COMMIT" || {
      echo "Cherry-pick failed; resolve manually."
      exit 2
    }
    echo "Cherry-pick landed on main."
    ;;

  *)
    echo "Unknown action: $ACTION" >&2
    exit 1
    ;;
esac
