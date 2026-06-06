# Engram Deployment Guide

## Architecture

```text
Internet -> Tailscale Serve (Mac mini:5001) -> 127.0.0.1:5001 (Flask API)
```

Tailscale Serve proxies inbound requests to the local Flask API at `127.0.0.1:5001`.

The deployed API must bind to `127.0.0.1:5001` for this flow. The development server may still use its default host when running locally outside launchd.

## Prerequisites

- macOS with Tailscale installed and serving on port `5001`
- PostgreSQL available locally at `postgresql://engram:engram@localhost:5432/engram`
- Python 3.11+ with the repo virtualenv at `/Volumes/lex1t/dev/shared/repos/engram/venv/`
- The checked-in LaunchAgent copied to `~/Library/LaunchAgents/com.engram.api.plist`

## Quick Deploy

```bash
cd /Volumes/lex1t/dev/shared/repos/engram
cp com.engram.api.plist ~/Library/LaunchAgents/com.engram.api.plist
plutil -lint ~/Library/LaunchAgents/com.engram.api.plist
./scripts/engram-deploy.sh
```

The deploy script:

1. Builds the React frontend with Vite.
2. Stops any running launchd-managed Engram API.
3. Starts the API via the checked-in LaunchAgent.
4. Verifies `http://127.0.0.1:5001/api/v4/health`.
5. Prints the local and Tailscale endpoints.

## LaunchAgent

The API is managed by `~/Library/LaunchAgents/com.engram.api.plist`.

This LaunchAgent:

- runs as your user,
- restarts automatically via `KeepAlive`,
- starts the Flask app by importing `create_app()` from `app.py`,
- sets `FLASK_ENV=production`,
- sets `DATABASE_URL=postgresql://engram:engram@localhost:5432/engram`,
- binds the production API to `127.0.0.1:5001`.

Install or refresh it with:

```bash
cp /Volumes/lex1t/dev/shared/repos/engram/com.engram.api.plist ~/Library/LaunchAgents/com.engram.api.plist
plutil -lint ~/Library/LaunchAgents/com.engram.api.plist
```

Start or restart it with:

```bash
launchctl unload ~/Library/LaunchAgents/com.engram.api.plist 2>/dev/null || true
sleep 2
launchctl load ~/Library/LaunchAgents/com.engram.api.plist
```

## Manual Checks

Health:

```bash
curl http://127.0.0.1:5001/api/v4/health
curl https://danishs-mac-mini.tail003386.ts.net:5001/api/v4/health
```

Logs:

```bash
tail -f /tmp/engram-api.log
tail -f /tmp/engram-deploy.log
```

Port ownership:

```bash
lsof -ti :5001 | xargs ps -p 2>/dev/null
```

## Tailscale Serve

Serve is configured to proxy:

```text
https://danishs-mac-mini.tail003386.ts.net:5001 -> http://127.0.0.1:5001
```

Inspect it with:

```bash
tailscale serve status
tailscale serve status --json
```

Reset it if needed:

```bash
tailscale serve reset
tailscale serve --bg 5001
```

## Troubleshooting

If the API is not reachable through Tailscale:

```bash
curl http://127.0.0.1:5001/api/v4/health
tailscale serve status --json
```

If restart leaves port `5001` busy:

- check for another process with `lsof -ti :5001 | xargs ps -p 2>/dev/null`,
- if it is a transient TIME_WAIT state, wait 30-60 seconds and retry.

If the frontend build fails:

```bash
cd /Volumes/lex1t/dev/shared/repos/engram/ui
npx vite build --debug 2>&1 | tail -30
```
