#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"

if [[ ! -d "${BACKEND_DIR}" ]]; then
  echo "Backend directory not found at ${BACKEND_DIR}" >&2
  exit 1
fi

cd "${BACKEND_DIR}"

if ! command -v uvicorn >/dev/null 2>&1; then
  echo "uvicorn is not available on PATH. Activate your environment and install backend requirements." >&2
  exit 1
fi

if [[ "${RUN_MIGRATIONS:-0}" == "1" ]]; then
  if ! command -v alembic >/dev/null 2>&1; then
    echo "alembic is not available on PATH, but RUN_MIGRATIONS=1 was requested." >&2
    exit 1
  fi
  echo "Running Alembic migrations..."
  alembic upgrade head
fi

HOST="${BACKEND_HOST:-0.0.0.0}"
PORT="${BACKEND_PORT:-8000}"
RELOAD="${BACKEND_RELOAD:-1}"

CMD=(uvicorn app.main:app --host "${HOST}" --port "${PORT}")
if [[ "${RELOAD}" == "1" ]]; then
  CMD+=(--reload)
fi

echo "Starting backend from ${BACKEND_DIR}"
echo "Command: ${CMD[*]}"
exec "${CMD[@]}"
