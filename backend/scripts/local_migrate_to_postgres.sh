#!/usr/bin/env bash
# local_migrate_to_postgres.sh — Set up local PostgreSQL and migrate from SQLite
# Cross‑platform note: this is for Linux/macOS. Use the .bat script on Windows.

set -euo pipefail

# Configuration (can be overridden via env)
POSTGRES_HOST=${POSTGRES_HOST:-localhost}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_SUPERUSER=${POSTGRES_SUPERUSER:-postgres}
POSTGRES_SUPERPASS=${POSTGRES_SUPERPASS:-}
POSTGRES_DB=${POSTGRES_DB:-clerk_community_admin}
POSTGRES_USER=${POSTGRES_USER:-clerk_user}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-clerk_password}

# Optional: Path to SQLite source for data migration
SQLITE_URL_DEFAULT="sqlite:///./backend/instance/community_admin.db"
DATABASE_URL_SQLITE=${DATABASE_URL_SQLITE:-$SQLITE_URL_DEFAULT}

# Behavior flags
AUTO_MIGRATE_DATA=${AUTO_MIGRATE_DATA:-ask} # values: ask|yes|no

ROOT_DIR=$(cd "$(dirname "$0")"/../.. && pwd)
BACKEND_DIR="$ROOT_DIR/backend"

export PGPASSWORD="$POSTGRES_SUPERPASS"

die() { echo "[ERROR] $*" >&2; exit 1; }
info() { echo "[INFO] $*"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Command not found: $1. Please install it and ensure it is on PATH."
}

require_cmd psql
if command -v pg_isready >/dev/null 2>&1; then
  info "Checking PostgreSQL availability at $POSTGRES_HOST:$POSTGRES_PORT..."
  if ! pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -q; then
    die "PostgreSQL does not appear to be running at $POSTGRES_HOST:$POSTGRES_PORT. Start it and retry."
  fi
else
  info "pg_isready not found; will rely on psql connection attempts."
fi

# Helper to run psql as superuser
psql_su() {
  PGPASSWORD="$POSTGRES_SUPERPASS" psql -v ON_ERROR_STOP=1 \
    -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_SUPERUSER" "$@"
}

# Check/create role
ROLE_EXISTS=$(psql_su -tAc "SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_USER'") || true
if [[ "$ROLE_EXISTS" != "1" ]]; then
  info "Creating role $POSTGRES_USER..."
  psql_su -c "CREATE ROLE \"$POSTGRES_USER\" LOGIN PASSWORD '$POSTGRES_PASSWORD';"
else
  info "Role $POSTGRES_USER already exists."
fi

# Check/create database
DB_EXISTS=$(psql_su -tAc "SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'") || true
if [[ "$DB_EXISTS" != "1" ]]; then
  info "Creating database $POSTGRES_DB owned by $POSTGRES_USER..."
  psql_su -c "CREATE DATABASE \"$POSTGRES_DB\" OWNER \"$POSTGRES_USER\";"
else
  info "Database $POSTGRES_DB already exists."
fi

# Grants and schema ownership
info "Granting privileges and setting schema ownership..."
psql_su -d "$POSTGRES_DB" -c "GRANT ALL PRIVILEGES ON DATABASE \"$POSTGRES_DB\" TO \"$POSTGRES_USER\";"
psql_su -d "$POSTGRES_DB" -c "ALTER SCHEMA public OWNER TO \"$POSTGRES_USER\";"
psql_su -d "$POSTGRES_DB" -c "GRANT USAGE, CREATE ON SCHEMA public TO \"$POSTGRES_USER\";"

# Optional extensions (uncomment to enable by default)
# psql_su -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
# psql_su -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

# Export DATABASE_URL for Alembic/app
export DATABASE_URL="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"
export POSTGRES_URL="$DATABASE_URL"

info "DATABASE_URL=$DATABASE_URL"

# Reset Alembic state (safe if not exists)
require_cmd python
info "Resetting Alembic version table (if present)..."
python "$BACKEND_DIR/scripts/reset_alembic.py"

# Run migrations
require_cmd alembic
info "Running Alembic migrations..."
cd "$BACKEND_DIR"
alembic upgrade head

# Optional data migration from SQLite
maybe_migrate() {
  case "$AUTO_MIGRATE_DATA" in
    yes) return 0 ;;
    no) return 1 ;;
    *)
      read -r -p "Migrate existing data from SQLite ($DATABASE_URL_SQLITE)? [y/N] " ans
      [[ "$ans" =~ ^[Yy]$ ]] && return 0 || return 1
      ;;
  esac
}

if maybe_migrate; then
  info "Starting data migration from SQLite to PostgreSQL..."
  python "$BACKEND_DIR/scripts/migrate_sqlite_to_postgres.py" \
    --source "$DATABASE_URL_SQLITE" \
    --target "$DATABASE_URL" || die "Data migration failed"
else
  info "Skipping data migration."
fi

# Validate with model tests
info "Validating database with model sanity tests..."
python "$BACKEND_DIR/scripts/test_models.py"

info "Local PostgreSQL setup and migration completed successfully."
