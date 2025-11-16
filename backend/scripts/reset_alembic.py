#!/usr/bin/env python3
"""
Reset Alembic state by dropping the alembic_version table if it exists.

Usage:
  - From project root (or backend/), with backend deps installed:
      python backend/scripts/reset_alembic.py

This script reads the database URL the same way Alembic does:
  - Prefer application config `app.config.get_database_url()`
  - Fall back to env var `DATABASE_URL`
  - Finally, fall back to value in alembic.ini if needed (not used here)

It is safe to run multiple times. Works for PostgreSQL and SQLite.
"""

from __future__ import annotations

import sys
from sqlalchemy import create_engine, text


def get_database_url() -> str:
    try:
        # Reuse application logic that assembles URL from env settings
        from app.config import get_database_url as app_get_db_url  # type: ignore

        url = app_get_db_url()
        if url:
            return url
    except Exception:
        pass

    import os
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    raise SystemExit("DATABASE_URL is not set and app.config could not provide a URL.")


def main() -> None:
    url = get_database_url()
    engine = create_engine(url, pool_pre_ping=True, future=True,
                           connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    ddl = "DROP TABLE IF EXISTS alembic_version"
    # For PostgreSQL, CASCADE is not necessary, but harmless if present.
    if url.startswith("postgresql"):
        ddl = ddl + " CASCADE"

    with engine.begin() as conn:
        conn.execute(text(ddl))
    print("Dropped alembic_version (if it existed). You can now start fresh with migrations.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error resetting Alembic: {exc}", file=sys.stderr)
        raise
