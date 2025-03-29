#!/bin/bash
set -e

# Run init *before* launching Postgres
echo "Running schema init (will retry if Postgres not ready)..."
until psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /usr/local/bin/pg-init.sql > /dev/null 2>&1; do
  echo "Postgres not ready, retrying schema init..."
  sleep 1
done

# Now start Postgres as the main process
exec docker-entrypoint.sh postgres
