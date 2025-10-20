#!/usr/bin/env sh
set -e

# If the container's data DB is missing but a repo DB exists, bootstrap from it
if [ ! -f /app/data/community_admin.db ] && [ -f /app/community_admin.db ]; then
  echo "Bootstrapping SQLite DB from repository copy..."
  mkdir -p /app/data
  cp /app/community_admin.db /app/data/community_admin.db
fi

echo "Running database migrations..."
# Use module form to avoid PATH issues
python -m alembic upgrade head

echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
