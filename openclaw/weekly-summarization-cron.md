# Weekly Summarization (OpenClaw cron)

Registers an isolated cron job that runs **every Sunday at 9:00** in **Pacific** time. The job triggers Engram’s background summarizer over all areas (notes from the last 7 days).

## Prerequisites

- Engram API reachable from the OpenClaw Gateway host (e.g. `http://127.0.0.1:5001`).
- OpenClaw Gateway running with cron enabled.

## Register the job

Adjust `ENGRAM_URL` if your API is not on the default port.

```bash
ENGRAM_URL="http://127.0.0.1:5001"

openclaw cron add \
  --name "Weekly Summarization" \
  --cron "0 9 * * 0" \
  --tz "America/Los_Angeles" \
  --session isolated \
  --tools "exec" \
  --message "Run: curl -sS -X POST ${ENGRAM_URL}/api/v1/jobs/summarize -H 'Content-Type: application/json' -d '{\"granularity\":\"WEEKLY\"}' && curl -sS ${ENGRAM_URL}/api/v1/jobs/status"
```

This schedules the agent to execute `curl` against `POST /api/v1/jobs/summarize` with `granularity=WEEKLY`, then fetch job status. Grant the `exec` tool (or equivalent) so the agent can run the shell command.

## Verify

```bash
openclaw cron list
openclaw cron run "<job-id>"
```

## API reference

- `POST /api/v1/jobs/summarize` — body: `{ "granularity": "WEEKLY", "area_id": "<optional-uuid>" }`
- `GET /api/v1/jobs/status` — last job state (`idle`, `queued`, `running`, `completed`, `error`)
