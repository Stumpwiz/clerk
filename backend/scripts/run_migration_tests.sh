#!/usr/bin/env bash
# run_migration_tests.sh — Spin up a temporary PostgreSQL, run migrations and tests, then clean up.

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")"/../.. && pwd)
BACKEND_DIR="$ROOT_DIR/backend"

# Configuration (can be overridden)
POSTGRES_IMAGE=${POSTGRES_IMAGE:-postgres:16}
TEST_DB=${TEST_DB:-clerk_community_admin_test}
TEST_USER=${TEST_USER:-clerk_user}
TEST_PASSWORD=${TEST_PASSWORD:-clerk_password}
TEST_HOST=${POSTGRES_HOST:-}
TEST_PORT=${POSTGRES_PORT:-55432}
CONTAINER_NAME=${PG_TEST_CONTAINER_NAME:-clerk-pg-migration-tests}

info() { echo "[INFO] $*"; }
warn() { echo "[WARN] $*" >&2; }
die() { echo "[ERROR] $*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Command not found: $1"
}

cleanup_container() {
  if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    info "Stopping and removing container ${CONTAINER_NAME}..."
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  fi
}

start_temp_postgres() {
  require_cmd docker
  cleanup_container
  # Randomize host port if already in use
  if lsof -iTCP -sTCP:LISTEN -P | grep -q ":${TEST_PORT}\b"; then
    warn "Port ${TEST_PORT} in use; picking an ephemeral port"
    TEST_PORT=$(python - <<'PY'
import socket
s=socket.socket(); s.bind(("",0)); print(s.getsockname()[1])
PY
)
  fi
  info "Starting temporary PostgreSQL container ${CONTAINER_NAME} on port ${TEST_PORT}..."
  docker run -d --rm --name "$CONTAINER_NAME" \
    -e POSTGRES_PASSWORD="${TEST_PASSWORD}" \
    -p "${TEST_PORT}:5432" \
    "$POSTGRES_IMAGE" >/dev/null

  # Wait for readiness
  info "Waiting for PostgreSQL to become ready..."
  for i in {1..60}; do
    if docker exec "$CONTAINER_NAME" pg_isready -U postgres >/dev/null 2>&1; then
      break
    fi
    sleep 1
    if [ "$i" -eq 60 ]; then
      die "PostgreSQL did not become ready in time"
    fi
  done

  # Export connection parameters (container uses postgres superuser)
  export POSTGRES_HOST=localhost
  export POSTGRES_PORT="$TEST_PORT"
  export POSTGRES_SUPERUSER=postgres
  export POSTGRES_SUPERPASS="$TEST_PASSWORD"
  export POSTGRES_DB="$TEST_DB"
  export POSTGRES_USER="$TEST_USER"
  export POSTGRES_PASSWORD="$TEST_PASSWORD"
}

main() {
  cd "$ROOT_DIR"

  # If POSTGRES_HOST provided, assume local instance; else start a container
  if [ -z "${TEST_HOST}" ]; then
    trap cleanup_container EXIT
    start_temp_postgres
  else
    info "Using existing PostgreSQL at ${TEST_HOST}:${TEST_PORT}"
    export POSTGRES_HOST="${TEST_HOST}"
    export POSTGRES_PORT="${TEST_PORT}"
    export POSTGRES_SUPERUSER=${POSTGRES_SUPERUSER:-postgres}
    export POSTGRES_SUPERPASS=${POSTGRES_SUPERPASS:-}
    export POSTGRES_DB="$TEST_DB"
    export POSTGRES_USER="$TEST_USER"
    export POSTGRES_PASSWORD="$TEST_PASSWORD"
  fi

  # Run the local migration workflow against test DB; skip data migration
  export AUTO_MIGRATE_DATA=no
  info "Running migration workflow against test database..."
  bash "$BACKEND_DIR/scripts/local_migrate_to_postgres.sh"

  # Run tests
  require_cmd pytest
  info "Executing migration test suite..."
  export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
  (cd "$ROOT_DIR" && pytest -vv backend/tests)

  info "All migration tests passed."
}

main "$@"
