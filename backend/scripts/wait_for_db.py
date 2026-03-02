#!/usr/bin/env python3
"""
Wait for the database to be reachable before starting the backend.

Designed for PostgreSQL URLs, but will also treat non-Postgres URLs as ready
immediately.

Features:
- Reads DATABASE_URL from the environment via app.config
- Attempts to connect and run a trivial SELECT 1
- Retries with exponential backoff until success or timeout/retries are exceeded
- Optional command passthrough: args after "--" will be executed when ready

Usage examples:
  # Just wait until DB is ready (Postgres), then exit 0
  python backend/scripts/wait_for_db.py --timeout 120

  # Wait, then run alembic + uvicorn
  python backend/scripts/wait_for_db.py -- alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from typing import List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_db_url() -> str:
    # Defer to app.config which resolves oldEnv and path corrections
    try:
        from app.config import get_database_url

        return get_database_url()
    except Exception:
        # Fallback to raw env var
        return os.getenv("DATABASE_URL", "")


def make_engine(url: str) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        future=True,
    )


def db_ready(url: str) -> bool:
    if not url:
        # With no URL, there's nothing we can check; consider it ready to not block startup
        return True
    if not url.startswith("postgresql"):
        # We only actively wait for PostgreSQL; other schemes treated as ready
        return True
    try:
        engine = make_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def parse_args(argv: Optional[List[str]] = None) -> tuple[argparse.Namespace, List[str]]:
    parser = argparse.ArgumentParser(description="Wait for database readiness (PostgreSQL)")
    parser.add_argument("--timeout", type=int, default=120, help="Maximum seconds to wait before failing (default: 120)")
    parser.add_argument("--interval", type=float, default=1.0, help="Initial retry interval in seconds (default: 1.0)")
    parser.add_argument("--max-interval", type=float, default=10.0, help="Max retry interval (default: 10.0)")
    parser.add_argument("--quiet", action="store_true", help="Reduce log noise")

    if argv is None:
        argv = sys.argv[1:]

    # Support passthrough after "--"
    if "--" in argv:
        idx = argv.index("--")
        left = argv[:idx]
        right = argv[idx + 1 :]
    else:
        left, right = argv, []

    args = parser.parse_args(left)
    return args, right


def main() -> int:
    args, passthrough = parse_args()
    url = get_db_url()

    start = time.time()
    attempt = 0
    interval = max(0.1, args.interval)

    if not args.quiet:
        print(f"[wait-for-db] Using DATABASE_URL={url or '(empty)'}")

    while True:
        attempt += 1
        if db_ready(url):
            if not args.quiet:
                print(f"[wait-for-db] Database is ready (attempt {attempt}).")
            break

        elapsed = time.time() - start
        if elapsed >= args.timeout:
            print(f"[wait-for-db] Timed out after {int(elapsed)}s waiting for DB.")
            return 1

        if not args.quiet:
            print(f"[wait-for-db] Not ready yet; retrying in {interval:.1f}s (attempt {attempt})…")
        time.sleep(interval)
        interval = min(args.max_interval, interval * 1.7)

    if passthrough:
        # Execute the given command in a shell to allow chaining (&&, env expansion)
        cmd_str = " ".join(shlex.quote(x) for x in passthrough)
        if not args.quiet:
            print(f"[wait-for-db] Executing: {cmd_str}")
        # Use shell=True to support '&&' sequences
        return subprocess.call(cmd_str, shell=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
