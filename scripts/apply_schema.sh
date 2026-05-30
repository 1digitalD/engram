#!/usr/bin/env bash
# Apply the fresh v4 schema to both main and test databases.
# DESTRUCTIVE: This script drops and recreates all tables.
#   - DATABASE_URL    → production schema (use with extreme caution)
#   - TEST_DATABASE_URL → isolated test schema (default: same as DATABASE_URL)
#
# FOR PRODUCTION: Run only when you intentionally want a clean cutover.
# FOR TESTS: The test suite should use a SEPARATE test database instance.
#   Never point TEST_DATABASE_URL at the production database.
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

# ── Safety check: refuse to drop the production DB without explicit confirmation ──
if [[ "$DATABASE_URL" != *"test"* && "$DATABASE_URL" != *"engram_test"* ]]; then
    echo "WARNING: DATABASE_URL targets what looks like a PRODUCTION database."
    echo "  This script will DROP ALL TABLES in:"
    echo "  $DATABASE_URL"
    echo ""
    read -p "Type 'yes-destroy-production' to confirm: " confirm
    if [[ "$confirm" != "yes-destroy-production" ]]; then
        echo "Aborted."
        exit 1
    fi
fi

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
echo "Main DB schema applied"

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
echo "Test DB schema applied"

echo "Tables in test DB:"
psql "$TEST_DATABASE_URL" -c "\dt"
