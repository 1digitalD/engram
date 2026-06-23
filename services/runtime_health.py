"""Runtime health helpers shared by the API and app bootstrap."""

from html import escape

from extensions import db


def probe_database_connection():
    """Probe the configured database and return (is_ready, reason)."""
    try:
        db.session.execute(db.text("SELECT 1"))
        db.session.rollback()
        return True, None
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        return False, str(exc)


def backend_unavailable_payload(reason=None):
    payload = {
        "status": "error",
        "api": "v4",
        "error": "backend unavailable",
        "dependency": "postgres",
        "message": "Engram backend unavailable",
    }
    if reason:
        payload["reason"] = reason
    return payload


def backend_unavailable_html(reason=None):
    safe_reason = escape(reason) if reason else "Database connectivity check failed."
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Engram backend unavailable</title>
    <style>
      :root {{
        color-scheme: dark;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: #111827;
        color: #e5e7eb;
      }}
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: radial-gradient(circle at top, #1f2937 0, #111827 45%, #030712 100%);
      }}
      main {{
        max-width: 42rem;
        padding: 2rem 2.25rem;
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 1rem;
        background: rgba(15, 23, 42, 0.9);
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
      }}
      h1 {{
        margin: 0 0 0.5rem;
        font-size: 1.4rem;
      }}
      p {{
        margin: 0.5rem 0;
        line-height: 1.5;
      }}
      code {{
        display: block;
        margin-top: 1rem;
        padding: 0.9rem 1rem;
        overflow-x: auto;
        border-radius: 0.75rem;
        background: rgba(30, 41, 59, 0.9);
        color: #fca5a5;
        white-space: pre-wrap;
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>Engram backend unavailable</h1>
      <p>The application could not reach Postgres, so the API is returning 503 until the database is healthy again.</p>
      <code>{safe_reason}</code>
    </main>
  </body>
</html>
"""
