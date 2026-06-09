#!/usr/bin/env bash
# Snapshot the production Engram database before any schema change or deploy.
# Writes a timestamped dump to backups/ (gitignored).
# Exits non-zero if the dump is empty or missing.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$REPO_ROOT/backups"
mkdir -p "$BACKUP_DIR"

DB_URL="${DATABASE_URL:-postgresql://engram:engram@localhost:5432/engram}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/engram_${TIMESTAMP}.sql"

echo "[backup] Dumping $DB_URL → $OUT"
pg_dump "$DB_URL" > "$OUT"

SIZE=$(wc -c < "$OUT")
if [[ "$SIZE" -lt 1024 ]]; then
  echo "[backup] ERROR: dump is suspiciously small (${SIZE} bytes). Check connection and try again."
  rm -f "$OUT"
  exit 1
fi

echo "[backup] OK: ${SIZE} bytes written to $OUT"
echo "[backup] To restore: psql <target-db-url> < $OUT"
