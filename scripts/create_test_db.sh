#!/usr/bin/env bash
# Create the dedicated integration-test database inside the Compose `db`
# service. Safe to run repeatedly.
set -euo pipefail

DB_NAME="${1:-enrollio_test}"

docker compose exec -T db sh -s -- "$DB_NAME" <<'EOS'
set -e
db="$1"
exists=$(psql -U "$POSTGRES_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$db'")
if [ "$exists" != "1" ]; then
  createdb -U "$POSTGRES_USER" "$db"
  echo "Created database $db"
else
  echo "Database $db already exists"
fi
EOS
