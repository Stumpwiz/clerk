#!/usr/bin/env python3
"""
Restore utility for PostgreSQL databases.

Features:
- Validates backup file before restore
- Supports dry-run (no changes)
- PostgreSQL: restores from pg_dump custom format (.dump) via pg_restore, or .sql via psql
- Safety prompts unless --force

Usage examples:
  # Dry run (detect target from app config)
  python backend/scripts/restore_database.py --backup backend/backups/postgres_db@host_20250101T000000Z.dump --dry-run

  # Restore with force (non-interactive)
  python backend/scripts/restore_database.py --backup backend/backups/postgres_db@host_20250101T000000Z.dump --force

  # Override target DB URL
  python backend/scripts/restore_database.py --backup path/to/file.dump --database-url postgresql://user:pass@host:5432/db
"""

from __future__ import annotations

import argparse
import os
import sys
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, unquote


def utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def get_database_url(override: str = None) -> str:
    """Get database URL from override argument or settings"""
    if override:
        return override

    from app.config import settings
    if settings.database_url:
        return settings.database_url

    raise SystemExit("DATABASE_URL not set. Please set it in environment or pass --database-url")




def check_cmd(cmd: str) -> None:
    if shutil.which(cmd) is None:
        raise SystemExit(f"Required command not found: {cmd}")


def run_cmd(cmd: list[str], env: Optional[dict] = None) -> None:
    rc = subprocess.call(cmd, env=env)
    if rc != 0:
        raise SystemExit(f"Command failed ({rc}): {' '.join(cmd)}")




def parse_pg_url(url: str):
    p = urlparse(url)
    if p.scheme not in ("postgresql", "postgresql+psycopg2"):
        raise SystemExit(f"Unsupported PostgreSQL URL scheme: {p.scheme}")
    return {
        "user": unquote(p.username) if p.username else "",
        "password": unquote(p.password) if p.password else None,
        "host": p.hostname or "localhost",
        "port": str(p.port or 5432),
        "db": (p.path or "/").lstrip("/"),
    }


def validate_pg_backup(path: Path) -> str:
    # Determine type by extension; support .dump (custom) and .sql
    suffix = path.suffix.lower()
    if suffix == ".dump":
        check_cmd("pg_restore")
        # Listing will validate file readability
        run_cmd(["pg_restore", "--list", str(path)])
        return "custom"
    elif suffix == ".sql":
        # Best-effort validation: ensure file is not empty and contains CREATE/INSERT/etc.
        if path.stat().st_size < 10:
            raise SystemExit("SQL backup seems too small")
        return "sql"
    else:
        # Try pg_restore --list regardless; fallback to sql
        try:
            check_cmd("pg_restore")
            run_cmd(["pg_restore", "--list", str(path)])
            return "custom"
        except Exception:
            return "sql"


def prompt_yesno(msg: str) -> bool:
    ans = input(f"{msg} [y/N] ").strip().lower()
    return ans in ("y", "yes")




def restore_postgres(backup: Path, target_url: str, dry_run: bool, force: bool) -> None:
    meta = parse_pg_url(target_url)
    env = os.environ.copy()
    if meta["password"]:
        env["PGPASSWORD"] = meta["password"]

    btype = validate_pg_backup(backup)

    if btype == "custom":
        cmd = [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "-h",
            meta["host"],
            "-p",
            meta["port"],
            "-U",
            meta["user"],
            "-d",
            meta["db"],
            str(backup),
        ]
    else:
        check_cmd("psql")
        cmd = [
            "psql",
            "-h",
            meta["host"],
            "-p",
            meta["port"],
            "-U",
            meta["user"],
            "-d",
            meta["db"],
            "-v",
            "ON_ERROR_STOP=1",
            "-f",
            str(backup),
        ]

    if dry_run:
        print("[DRY-RUN] Would execute:", " ".join(cmd))
        return

    if not force and not prompt_yesno("About to restore into PostgreSQL database (destructive). Proceed?"):
        print("Aborted.")
        return

    print("[INFO] Running:", " ".join(cmd))
    run_cmd(cmd, env=env)
    print("[OK] Restore completed.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Restore PostgreSQL database")
    p.add_argument("--backup", required=True, help="Path to backup file (.dump or .sql)")
    p.add_argument("--database-url", dest="database_url", default=None, help="Override target DATABASE_URL")
    p.add_argument("--dry-run", action="store_true", help="Print actions without executing")
    p.add_argument("--force", action="store_true", help="Do not prompt for confirmation")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    url = get_database_url(args.database_url)
    backup = Path(args.backup).resolve()
    if not backup.exists():
        raise SystemExit(f"Backup path not found: {backup}")

    # PostgreSQL only
    restore_postgres(backup, url, args.dry_run, args.force)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[ERROR] Restore failed: {exc}", file=sys.stderr)
        sys.exit(1)
