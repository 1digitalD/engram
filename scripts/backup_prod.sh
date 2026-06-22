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

resolve_pg_binary() {
  local name="$1"
  local candidate
  local -a candidates=(
    "$(command -v "$name" 2>/dev/null || true)"
    "/opt/homebrew/opt/libpq/bin/$name"
    "/usr/local/opt/libpq/bin/$name"
    "/opt/homebrew/bin/$name"
    "/usr/local/bin/$name"
    "/Applications/Postgres.app/Contents/Versions/latest/bin/$name"
  )

  shopt -s nullglob
  for candidate in /opt/homebrew/Cellar/libpq/*/bin/"$name" /usr/local/Cellar/libpq/*/bin/"$name"; do
    candidates+=("$candidate")
  done
  for candidate in /opt/homebrew/Cellar/postgresql@*/*/bin/"$name" /usr/local/Cellar/postgresql@*/*/bin/"$name"; do
    candidates+=("$candidate")
  done
  shopt -u nullglob

  for candidate in "${candidates[@]}"; do
    if [[ -n "$candidate" && -x "$candidate" ]] && "$candidate" --version >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

PG_DUMP_BIN="$(resolve_pg_binary pg_dump || true)"
if [[ -z "$PG_DUMP_BIN" ]]; then
  echo "[backup] ERROR: could not find a working pg_dump binary."
  echo "[backup] Install libpq/Postgres CLI tools or add pg_dump to PATH."
  exit 1
fi

echo "[backup] Dumping $DB_URL → $OUT"
"$PG_DUMP_BIN" "$DB_URL" > "$OUT"

SIZE=$(wc -c < "$OUT")
if [[ "$SIZE" -lt 1024 ]]; then
  echo "[backup] ERROR: dump is suspiciously small (${SIZE} bytes). Check connection and try again."
  rm -f "$OUT"
  exit 1
fi

echo "[backup] OK: ${SIZE} bytes written to $OUT"
echo "[backup] Using pg_dump at: $PG_DUMP_BIN"
echo "[backup] To restore: psql <target-db-url> < $OUT"
