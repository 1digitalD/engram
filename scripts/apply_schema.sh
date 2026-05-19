#!/usr/bin/env bash
# Apply the fresh v4 schema to both main and test databases.
# This is intentionally destructive: v4 is a clean cutover with no migration.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Load .env for local use, but do not clobber explicit environment values.
if [ -f "$REPO_DIR/.env" ]; then
  while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    if [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && [ -z "${!key:-}" ]; then
      export "$key=$value"
    fi
  done < "$REPO_DIR/.env"
fi

DATABASE_URL="${DATABASE_URL:?DATABASE_URL not set}"
TEST_DATABASE_URL="${TEST_DATABASE_URL:-$DATABASE_URL}"

echo "Applying schema to main DB..."
psql -v ON_ERROR_STOP=1 "$DATABASE_URL" -c "
DO \$\$ DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
    END LOOP;
END \$\$;
"
psql -v ON_ERROR_STOP=1 "$DATABASE_URL" -f "$REPO_DIR/docs/SCHEMA.sql"
echo "✓ Main DB schema applied"

echo "Applying schema to test DB..."
psql -v ON_ERROR_STOP=1 "$TEST_DATABASE_URL" -c "
DO \$\$ DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
    END LOOP;
END \$\$;
"
psql -v ON_ERROR_STOP=1 "$TEST_DATABASE_URL" -f "$REPO_DIR/docs/SCHEMA.sql"
echo "✓ Test DB schema applied"

echo "Tables in test DB:"
psql "$TEST_DATABASE_URL" -c "\dt"
