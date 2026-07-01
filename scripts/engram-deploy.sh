#!/usr/bin/env bash
# engram-deploy.sh — Build UI and restart the launchd-managed API.
set -euo pipefail

ENGRAM_DIR="/Volumes/lex1t/dev/shared/repos/engram"
LAUNCH_AGENT="${HOME}/Library/LaunchAgents/com.engram.api.plist"
API_PORT=5001
TAILSCALE_HOST="danishs-mac-mini.tail003386.ts.net"
DEFAULT_LOG_DIR="${HOME}/Library/Logs"
DEFAULT_LOG_FILE="${DEFAULT_LOG_DIR}/engram-deploy.log"
LOG_FILE="${ENGRAM_DEPLOY_LOG:-$DEFAULT_LOG_FILE}"
API_BASE="http://127.0.0.1:${API_PORT}/api/v4"

prepare_log_file() {
  mkdir -p "$DEFAULT_LOG_DIR"

  if [[ -e "$LOG_FILE" && ! -w "$LOG_FILE" ]]; then
    LOG_FILE="${DEFAULT_LOG_DIR}/engram-deploy-${USER}.log"
  fi

  touch "$LOG_FILE"
}

log() {
  echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

fetch_json() {
  local path="$1"
  curl -fsS "${API_BASE}${path}"
}

smoke_endpoint() {
  local label="$1"
  local path="$2"
  local python_check="$3"
  local body

  log "Smoke: ${label}"
  body="$(fetch_json "$path")"
  python3 -c "$python_check" "$body"
}

run_smoke_suite() {
  smoke_endpoint \
    "health" \
    "/health" \
    'import json, sys; data = json.loads(sys.argv[1]); assert data.get("status") == "ok"; assert data.get("api") == "v4"'

  smoke_endpoint \
    "summary" \
    "/summary" \
    'import json, sys; data = json.loads(sys.argv[1]); assert "today_count" in data; assert "threads_count" in data'

  smoke_endpoint \
    "now feed (/today)" \
    "/today" \
    'import json, sys; data = json.loads(sys.argv[1]); assert "overdue" in data; assert "recent_notes" in data; assert "delegations_quiet" in data'

  smoke_endpoint \
    "threads" \
    "/threads?rank=attention&limit=1" \
    'import json, sys; data = json.loads(sys.argv[1]); assert isinstance(data.get("threads"), list)'

  smoke_endpoint \
    "memory timeline" \
    "/timeline?limit=1" \
    'import json, sys; data = json.loads(sys.argv[1]); assert "events" in data; assert "next_offset" in data'
}

cd "$ENGRAM_DIR"
prepare_log_file

if [[ ! -f "$LAUNCH_AGENT" ]]; then
  log "ERROR: LaunchAgent not installed at $LAUNCH_AGENT"
  log "Install it with: cp $ENGRAM_DIR/com.engram.api.plist $LAUNCH_AGENT"
  exit 1
fi

log "Creating production backup..."
bash "$ENGRAM_DIR/scripts/backup_prod.sh"

log "Validating LaunchAgent plist..."
plutil -lint "$LAUNCH_AGENT" >/dev/null

log "Building frontend..."
(
  cd ui
  npm run build
)

log "Stopping old API (launchd)..."
launchctl unload "$LAUNCH_AGENT" 2>/dev/null || true
sleep 2

log "Starting API via launchd..."
launchctl load "$LAUNCH_AGENT"
sleep 4

log "Running focused runtime smoke suite..."
if ! run_smoke_suite; then
  log "ERROR: deploy smoke failed"
  tail -20 /tmp/engram-api.log || true
  exit 1
fi

log "Deploy log: $LOG_FILE"
log "API up at http://127.0.0.1:${API_PORT}"
log "Tailscale endpoint: https://${TAILSCALE_HOST}:${API_PORT}"
log "Done."
