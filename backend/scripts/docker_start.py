#!/usr/bin/env python3
"""
Container startup orchestrator for the backend service.

Responsibilities:
- Resolve `DATABASE_URL` using the app config (supports POSTGRES_* pieces)
- If using PostgreSQL: wait for readiness, then run Alembic `upgrade head`
- If using SQLite (or DATABASE_URL is empty): skip migrations
- Finally, start Uvicorn to serve the FastAPI app

Configurable via environment variables:
- DATABASE_URL or POSTGRES_*  (resolved by app.config.get_database_url)
- API_HOST (default: 0.0.0.0)
- API_PORT (default: 8000)
- UVICORN_WORKERS (default: 1)
- DISABLE_AUTO_MIGRATE (default: "false") — set to "true" to skip Alembic

This script is idempotent and safe to run at container start; Alembic will
only apply pending migrations.
"""

from __future__ import annotations

import os
import sys
import subprocess
from typing import List

from sqlalchemy import create_engine, text


def get_database_url() -> str:
    try:
        from app.config import get_database_url as app_get_db_url  # type: ignore

        url = app_get_db_url()
        if url:
            return url
    except Exception:
        pass
    return os.getenv("DATABASE_URL", "")


def is_postgres(url: str) -> bool:
    return url.startswith("postgresql")


def wait_for_db(url: str, timeout: int = 120) -> None:
    """Defer to the existing wait_for_db.py helper to avoid code duplication."""
    # In Docker container, paths are relative to /app workdir
    wait_script = "scripts/wait_for_db.py" if os.path.exists("scripts/wait_for_db.py") else "backend/scripts/wait_for_db.py"
    cmd: List[str] = [
        sys.executable,
        wait_script,
        "--timeout",
        str(timeout),
    ]
    rc = subprocess.call(cmd)
    if rc != 0:
        raise SystemExit(rc)


def run_alembic_upgrade() -> None:
    # Run Alembic - handle both Docker (workdir=/app) and local (workdir=project root)
    env = os.environ.copy()
    # In Docker container, alembic.ini is at /app/alembic.ini (no backend/ subdir)
    # Locally, it's at backend/alembic.ini
    if os.path.exists("alembic.ini"):
        # Docker: already in /app, alembic.ini is here
        rc = subprocess.call(["alembic", "upgrade", "head"], env=env)
    elif os.path.exists("backend/alembic.ini"):
        # Local: need to cd to backend/
        rc = subprocess.call(["alembic", "upgrade", "head"], cwd="backend", env=env)
    else:
        print("ERROR: Cannot find alembic.ini", file=sys.stderr)
        raise SystemExit(1)

    if rc != 0:
        raise SystemExit(rc)


def start_uvicorn() -> None:
    host = os.getenv("API_HOST", "0.0.0.0")
    port = os.getenv("API_PORT", "8000")
    workers = os.getenv("UVICORN_WORKERS", "1")
    cmd = [
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    # Only set workers if >1 to avoid issues in debug/reload
    try:
        if int(workers) > 1:
            cmd += ["--workers", str(workers)]
    except ValueError:
        pass

    os.execvp(cmd[0], cmd)  # replaces current process


def main() -> None:
    url = get_database_url()
    disable_auto_migrate = os.getenv("DISABLE_AUTO_MIGRATE", "false").lower() in ("1", "true", "yes")

    if is_postgres(url):
        # Wait for DB to be ready
        wait_for_db(url, timeout=120)
        # Optionally run Alembic
        if not disable_auto_migrate:
            run_alembic_upgrade()
    else:
        # SQLite or empty URL — skip migrations
        pass

    # Start API server
    start_uvicorn()


if __name__ == "__main__":
    main()
