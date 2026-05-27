#!/usr/bin/env bash
# One-shot migration: bring entity_events.event_type CHECK constraint in line
# with the current SCHEMA.sql allow-list. Older deployments are missing
# 'ai_updated' and 'ai_summarized', which causes 500s when AI flows
# (e.g. capture's AI-generated title path) try to write events.
#
# Idempotent: drops the constraint by name (IF EXISTS) and re-adds the full list.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -f "$REPO_DIR/.env" ]; then
  while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    if [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && [ -z "${!key:-}" ]; then
      export "$key=$value"
    fi
  done < "$REPO_DIR/.env"
fi

DATABASE_URL="${DATABASE_URL:?DATABASE_URL not set}"

psql -v ON_ERROR_STOP=1 "$DATABASE_URL" <<'SQL'
ALTER TABLE entity_events DROP CONSTRAINT IF EXISTS entity_events_event_type_check;
ALTER TABLE entity_events ADD CONSTRAINT entity_events_event_type_check
  CHECK (event_type IN (
    'created', 'updated', 'status_changed', 'archived', 'deleted',
    'relationship_added', 'relationship_removed',
    'tag_added', 'tag_removed', 'ai_processed', 'ai_updated', 'ai_summarized',
    'suggestion_accepted', 'suggestion_dismissed'
  ));
SQL

echo "✓ entity_events_event_type_check now matches docs/SCHEMA.sql"
