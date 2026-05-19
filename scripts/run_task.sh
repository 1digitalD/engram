#!/usr/bin/env bash
# Legacy agent task runner retired for Engram v4.
set -euo pipefail

cat >&2 <<'MESSAGE'
scripts/run_task.sh is retired.

Engram v4 is a clean cutover driven by docs/V4_PRINCIPLES.md and
docs/V4_IMPLEMENTATION_PLAN.md. The old AGENT_PLAN task runner is not a v4
workflow and must not be used for new implementation work.
MESSAGE

exit 1
