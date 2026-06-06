#!/usr/bin/env bash
# engram-deploy.sh — Build the UI and restart the launchd-managed API.
set -euo pipefail

ENGRAM_DIR="/Volumes/lex1t/dev/shared/repos/engram"
LAUNCH_AGENT="${HOME}/Library/LaunchAgents/com.engram.api.plist"
API_PORT=5001
TAILSCALE_HOST="danishs-mac-mini.tail003386.ts.net"
LOG_FILE="/tmp/engram-deploy.log"

log() {
  echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cd "$ENGRAM_DIR"

if [[ ! -f "$LAUNCH_AGENT" ]]; then
  log "ERROR: LaunchAgent not installed at $LAUNCH_AGENT"
  log "Install it with: cp $ENGRAM_DIR/com.engram.api.plist $LAUNCH_AGENT"
  exit 1
fi

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

log "Verifying API health..."
if ! curl -sf "http://127.0.0.1:${API_PORT}/api/v4/health" >/dev/null; then
  log "ERROR: API failed to start on port ${API_PORT}"
  tail -20 /tmp/engram-api.log || true
  exit 1
fi

log "API up at http://127.0.0.1:${API_PORT}"
log "Tailscale endpoint: https://${TAILSCALE_HOST}:${API_PORT}"
log "Done."
