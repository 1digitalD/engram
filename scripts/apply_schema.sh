#!/usr/bin/env bash
# Apply SCHEMA.sql to both main and test databases.
# Run this after C1-INFRA completes, before starting the overnight build.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$REPO_DIR/.env" ] && source "$REPO_DIR/.env"

DATABASE_URL="${DATABASE_URL:?DATABASE_URL not set}"
TEST_DATABASE_URL="${TEST_DATABASE_URL:?TEST_DATABASE_URL not set}"

echo "Applying schema to main DB..."
psql "$DATABASE_URL" -f "$REPO_DIR/docs/SCHEMA.sql"
echo "✓ Main DB schema applied"

echo "Applying schema to test DB..."
psql "$TEST_DATABASE_URL" -f "$REPO_DIR/docs/SCHEMA.sql"
echo "✓ Test DB schema applied"

echo "Tables in test DB:"
psql "$TEST_DATABASE_URL" -c "\dt"
