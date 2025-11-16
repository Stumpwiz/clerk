#!/usr/bin/env python3
"""
Restore utility for SQLite and PostgreSQL databases.

Features:
- Validates backup file before restore
- Supports dry-run (no changes)
- SQLite: backs up current DB, then restores from .db file
- PostgreSQL: restores from pg_dump custom format (.dump) via pg_restore, or .sql via psql
- Safety prompts unless --force

Usage examples:
  # Dry run (detect target from app config)
  python backend/scripts/restore_database.py --backup backend/backups/postgres_db@host_20250101T000000Z.dump --dry-run

  # Restore with force (non-interactive)
  python backend/scripts/restore_database.py --backup backend/backups/sqlite_community_admin.db_20250101T000000Z.db --force

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


def get_database_url(cli_url: Optional[str]) -> str:
    if cli_url:
        return cli_url
    try:
        from app.config import get_database_url as app_get_db_url  # type: ignore

        url = app_get_db_url()
        if url:
            return url
    except Exception:
        pass
    env_url = os.getenv("DATABASE_URL")
    if not env_url:
        raise SystemExit("DATABASE_URL not set and app.config could not provide one.")
    return env_url


def is_sqlite_url(url: str) -> bool:
    return url.startswith("sqlite:")


def resolve_sqlite_path(url: str) -> Path:
    if not url.startswith("sqlite///") and not url.startswith("sqlite:///"):
        # normalize if needed
        pass
    if not url.startswith("sqlite:///"):
        raise SystemExit(f"Unsupported SQLite URL: {url}")
    path_str = url.replace("sqlite:///", "", 1)
    if path_str.startswith("./"):
        backend_dir = Path(__file__).resolve().parents[2] / "backend"
        return (backend_dir / path_str[2:]).resolve()
    return Path(path_str).resolve()


def check_cmd(cmd: str) -> None:
    if shutil.which(cmd) is None:
        raise SystemExit(f"Required command not found: {cmd}")


def run_cmd(cmd: list[str], env: Optional[dict] = None) -> None:
    rc = subprocess.call(cmd, env=env)
    if rc != 0:
        raise SystemExit(f"Command failed ({rc}): {' '.join(cmd)}")


def validate_sqlite_backup(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Backup not found: {path}")
    with path.open("rb") as f:
        header = f.read(16)
    if not header.startswith(b"SQLite format 3\x00"):
        raise SystemExit("Backup file does not appear to be SQLite .db format")


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


def restore_sqlite(backup: Path, target_url: str, dry_run: bool, force: bool) -> None:
    target_path = resolve_sqlite_path(target_url)
    validate_sqlite_backup(backup)
    target_dir = target_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    pre_backup = target_dir / f"{target_path.name}.pre-restore.{utc_ts()}"

    if dry_run:
        print(f"[DRY-RUN] Would backup current DB to: {pre_backup}")
        print(f"[DRY-RUN] Would restore SQLite from {backup} to {target_path}")
        return

    if target_path.exists():
        if not force and not prompt_yesno(f"About to overwrite {target_path}. Proceed?"):
            print("Aborted.")
            return
        shutil.copy2(str(target_path), str(pre_backup))
        print(f"[OK] Saved pre-restore copy: {pre_backup}")

    shutil.copy2(str(backup), str(target_path))
    print(f"[OK] Restored SQLite database to: {target_path}")


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
    p = argparse.ArgumentParser(description="Restore database (SQLite or PostgreSQL)")
    p.add_argument("--backup", required=True, help="Path to backup file (.db, .dump, or .sql)")
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

    if is_sqlite_url(url):
        restore_sqlite(backup, url, args.dry_run, args.force)
    else:
        restore_postgres(backup, url, args.dry_run, args.force)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[ERROR] Restore failed: {exc}", file=sys.stderr)
        sys.exit(1)
