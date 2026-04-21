#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"

if [[ ! -d "${FRONTEND_DIR}" ]]; then
  echo "Frontend directory not found at ${FRONTEND_DIR}" >&2
  exit 1
fi

cd "${FRONTEND_DIR}"

if [[ ! -f "package.json" ]]; then
  echo "package.json not found in ${FRONTEND_DIR}" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is not available on PATH." >&2
  exit 1
fi

HOST="${FRONTEND_HOST:-0.0.0.0}"
PORT="${FRONTEND_PORT:-3000}"
CLEAN_NEXT="${FRONTEND_CLEAN_NEXT:-0}"

if [[ "${CLEAN_NEXT}" == "1" ]]; then
  echo "Removing .next build cache..."
  rm -rf .next
fi

echo "Starting frontend from ${FRONTEND_DIR}"
echo "Command: npm run dev -- --hostname ${HOST} --port ${PORT}"
exec npm run dev -- --hostname "${HOST}" --port "${PORT}"
