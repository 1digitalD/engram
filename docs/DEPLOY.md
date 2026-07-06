# Engram Deployment Guide

## Architecture

```text
Tailscale Serve (tailnet)
  |-- :5001 -> 127.0.0.1:5001  Flask API + built Vite UI
  |-- :8765 -> 127.0.0.1:8765  MCP HTTP (streamable-http at /mcp)
```

Current runtime expectations:

- Runtime API surface is `/api/v4` only.
- The app shell redirects `/` to `/now`.
- Primary top-level UI lenses are `/now`, `/threads`, `/memory`, and `/recall`.
- `/api/v4/inbox` still exists as backend review data, but it is not the primary app landing route.

## Prerequisites

- macOS with Tailscale installed and serving on ports `5001` (API/UI) and `8765` (MCP)
- PostgreSQL available locally at `postgresql://engram:engram@localhost:5432/engram`
- Python 3.11+ and the repo virtualenv at `/Volumes/lex1t/dev/shared/repos/engram/venv/`
- checked-in LaunchAgents copied to `~/Library/LaunchAgents/`:
  - `com.engram.api.plist` — Flask API on `127.0.0.1:5001`
  - `com.engram.mcp.plist` — MCP HTTP on `127.0.0.1:8765` (set `MCP_ALLOWED_HOSTS` to your Tailscale DNS name)

## Quick Deploy

```bash
cd /Volumes/lex1t/dev/shared/repos/engram
cp com.engram.api.plist ~/Library/LaunchAgents/com.engram.api.plist
plutil -lint ~/Library/LaunchAgents/com.engram.api.plist
./scripts/engram-deploy.sh
```

The deploy script:

1. Creates a production backup via `scripts/backup_prod.sh`.
2. Builds the React frontend with Vite.
3. Stops any running launchd-managed Engram API.
4. Starts the API via the checked-in LaunchAgent.
5. Runs a focused smoke suite against the live local service:
   `GET /api/v4/health`, `GET /api/v4/summary`, `GET /api/v4/today`,
   `GET /api/v4/threads?rank=attention&limit=1`, and `GET /api/v4/timeline?limit=1`.
6. Prints the local and Tailscale endpoints.

The smoke suite is intentionally read-only and aimed at the current user-facing runtime:

- `health` proves the process booted and can reach Postgres.
- `summary` matches the shell counts used by the top navigation.
- `today` validates the `/now` feed payload.
- `threads` validates the `/threads` lens payload.
- `timeline` validates the `/memory` lens payload.

`scripts/backup_prod.sh` auto-discovers a working `pg_dump` binary from `PATH`,
Homebrew `libpq`, or common Postgres.app installs. `scripts/engram-deploy.sh`
writes its log to `~/Library/Logs/engram-deploy.log` by default, and falls back
to `~/Library/Logs/engram-deploy-$USER.log` if the requested path is not writable.

## LaunchAgent

The API is managed by `~/Library/LaunchAgents/com.engram.api.plist`. This LaunchAgent:

- runs as the current user
- restarts automatically via `KeepAlive`
- starts the Flask app by importing `create_app()` from `app.py`
- sets `FLASK_ENV=production`
- sets `DATABASE_URL=postgresql://engram:engram@127.0.0.1:5432/engram`
- binds the production API to `127.0.0.1:5001`

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

### MCP (`com.engram.mcp`)

The MCP HTTP server is managed by `~/Library/LaunchAgents/com.engram.mcp.plist`. It:

- runs `mcp_server/server.py` with `TRANSPORT=http` on `127.0.0.1:8765`
- proxies to the local API via `ENGRAM_API_BASE=http://127.0.0.1:5001/api/v4`
- sets `MCP_ALLOWED_HOSTS` to the Tailscale DNS name so FastMCP accepts proxied requests

Install or refresh it with:

```bash
cp /Volumes/lex1t/dev/shared/repos/engram/com.engram.mcp.plist ~/Library/LaunchAgents/com.engram.mcp.plist
plutil -lint ~/Library/LaunchAgents/com.engram.mcp.plist
launchctl unload ~/Library/LaunchAgents/com.engram.mcp.plist 2>/dev/null || true
sleep 2
launchctl load ~/Library/LaunchAgents/com.engram.mcp.plist
```

Remote MCP clients should use `https://<tailscale-host>:8765/mcp` (not port `5001`).

## Manual Checks

Health:

```bash
curl http://127.0.0.1:5001/api/v4/health
curl https://danishs-mac-mini.tail003386.ts.net:5001/api/v4/health
curl --http1.1 https://danishs-mac-mini.tail003386.ts.net:8765/mcp -o /dev/null -w "%{http_code}\n"
```

A `406` from `/mcp` without MCP client headers is expected; `421` means `MCP_ALLOWED_HOSTS`
needs updating in `com.engram.mcp.plist`.

Focused runtime smoke:

```bash
curl http://127.0.0.1:5001/api/v4/summary
curl http://127.0.0.1:5001/api/v4/today
curl "http://127.0.0.1:5001/api/v4/threads?rank=attention&limit=1"
curl "http://127.0.0.1:5001/api/v4/timeline?limit=1"
```

App shell route check:

```bash
curl -I http://127.0.0.1:5001/
curl -I http://127.0.0.1:5001/now
```

Logs:

```bash
tail -f /tmp/engram-api.log
tail -f ~/Library/Logs/engram-deploy.log
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
tailscale serve --bg --https=8765 8765
```

## MCP over Tailscale

The MCP HTTP server runs on `127.0.0.1:8765` via `com.engram.mcp` LaunchAgent.
Tailscale Serve proxies:

```text
https://danishs-mac-mini.tail003386.ts.net:8765 -> http://127.0.0.1:8765
```

MCP endpoint path: `/mcp` (streamable HTTP).

If remote clients see `421 Misdirected Request`, FastMCP is rejecting the
Tailscale `Host` header — not a certificate mismatch. Set `MCP_ALLOWED_HOSTS`
in `com.engram.mcp.plist` to your Tailscale machine name, then restart MCP:

```bash
cp /Volumes/lex1t/dev/shared/repos/engram/com.engram.mcp.plist ~/Library/LaunchAgents/com.engram.mcp.plist
plutil -lint ~/Library/LaunchAgents/com.engram.mcp.plist
launchctl unload ~/Library/LaunchAgents/com.engram.mcp.plist 2>/dev/null || true
sleep 2
launchctl load ~/Library/LaunchAgents/com.engram.mcp.plist
curl --http1.1 https://danishs-mac-mini.tail003386.ts.net:8765/mcp -o /dev/null -w "%{http_code}\n"
```

A `406` from `/mcp` without MCP client headers is expected; `421` means the host
allowlist still needs updating.

## Troubleshooting

If the API is not reachable through Tailscale:

```bash
curl http://127.0.0.1:5001/api/v4/health
tailscale serve status --json
```

If the deploy smoke fails after restart:

```bash
tail -40 /tmp/engram-api.log
tail -40 ~/Library/Logs/engram-deploy.log
curl http://127.0.0.1:5001/api/v4/health
curl http://127.0.0.1:5001/api/v4/summary
```

If restart leaves port `5001` busy:

- check for another process with `lsof -ti :5001 | xargs ps -p 2>/dev/null`
- if it is a transient TIME_WAIT state, wait 30-60 seconds and retry

If the frontend build fails:

```bash
cd /Volumes/lex1t/dev/shared/repos/engram/ui
npx vite build --debug 2>&1 | tail -30
```
