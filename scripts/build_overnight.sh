#!/usr/bin/env bash
# Legacy overnight task orchestrator retired for Engram v4.
set -euo pipefail

cat >&2 <<'MESSAGE'
scripts/build_overnight.sh is retired.

Engram v4 is implemented cycle by cycle from docs/V4_IMPLEMENTATION_PLAN.md.
The old overnight AGENT_PLAN workflow targeted obsolete pre-v4 work and must
not be used for v4 implementation.
MESSAGE

exit 1
