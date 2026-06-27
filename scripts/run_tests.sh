#!/bin/bash
# Wrapper to run pytest with correct test DB env.
# The test postgres container (engram-postgres_test-1) is configured with
# pg_hba.conf trust auth for the 127.0.0.1/0.0.0.0 range, so no password
# is required when connecting from the host (via the published 5433 port).
#
# Usage:
#   scripts/run_tests.sh [PATH] [pytest-args...]
#
# PATH defaults to the main repo. If given as an existing directory (worktree
# or repo), the script changes to that directory and uses the main repo's
# virtualenv (since worktrees don't carry venv/). This makes the wrapper safe
# to invoke from a Loopsmith validator that runs from the worktree path.
#
# Examples:
#   scripts/run_tests.sh tests/integration/test_v4_capture.py
#   scripts/run_tests.sh /Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/foo tests/integration/test_v4_capture.py

set -euo pipefail
MAIN_REPO="/Volumes/lex1t/dev/shared/repos/engram"
TEST_DIR="${MAIN_REPO}"

# If first argument is an existing directory (worktree or repo), use it as CWD.
if [[ $# -gt 0 && -d "$1" ]]; then
    TEST_DIR="$(cd "$1" && pwd)"
    shift
fi

cd "${TEST_DIR}"
unset PGPASSWORD
export PYTHONPATH="${TEST_DIR}"
export TEST_DATABASE_URL="postgresql://engram@127.0.0.1:5433/engram_test"
exec "${MAIN_REPO}/venv/bin/pytest" -q "$@"
