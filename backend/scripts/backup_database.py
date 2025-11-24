#!/usr/bin/env python3
"""
Backup utility for PostgreSQL databases.

Features:
- Detects database URL from application config (DATABASE_URL)
- Creates timestamped backups under backend/backups/
- PostgreSQL: uses pg_dump (custom format -Fc) for robust, restorable dumps
- Optional S3 upload via AWS CLI (aws s3 cp)
- Safety checks and clear output

Usage examples:
  # Use app config to resolve DATABASE_URL, backup locally
  python backend/scripts/backup_database.py

  # Upload to S3 after local backup
  python backend/scripts/backup_database.py --s3-bucket my-backups --s3-prefix clerk/prod

  # Override database URL
  python backend/scripts/backup_database.py --database-url postgresql://user:pass@host:5432/db
"""

from __future__ import annotations

import argparse
import os
import sys
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse, unquote
from app.config import settings


BACKUPS_DIR = Path(__file__).resolve().parents[2] / "backend" / "backups"


def utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def get_database_url(override: str = None) -> str:
    """Get database URL from override argument or settings"""
    if override:
        return override

    from app.config import settings
    if settings.database_url:
        return settings.database_url

    raise SystemExit("DATABASE_URL not set. Please set it in environment or pass --database-url")


@dataclass
class PgConn:
    user: str
    password: Optional[str]
    host: str
    port: str
    db: str


def parse_pg_url(url: str) -> PgConn:
    p = urlparse(url)
    if p.scheme not in ("postgresql", "postgresql+psycopg2"):
        raise SystemExit(f"Unsupported PostgreSQL URL scheme: {p.scheme}")
    user = unquote(p.username) if p.username else ""
    password = unquote(p.password) if p.password else None
    host = p.hostname or "localhost"
    port = str(p.port or 5432)
    db = (p.path or "/").lstrip("/")
    if not db:
        raise SystemExit("PostgreSQL URL missing database name")
    return PgConn(user=user, password=password, host=host, port=port, db=db)



def check_cmd_exists(cmd: str) -> None:
    if shutil.which(cmd) is None:
        raise SystemExit(f"Required command not found on PATH: {cmd}")



def run_cmd(cmd: list[str], env: Optional[dict] = None) -> None:
    rc = subprocess.call(cmd, env=env)
    if rc != 0:
        raise SystemExit(f"Command failed ({rc}): {' '.join(cmd)}")



def backup_postgres(url: str, out_dir: Path) -> Path:
    check_cmd_exists("pg_dump")
    conn = parse_pg_url(url)
    ensure_dir(out_dir)
    ts = utc_ts()
    safe_host = conn.host.replace(":", "-")
    out_file = out_dir / f"postgres_{conn.db}@{safe_host}_{ts}.dump"

    env = os.environ.copy()
    if conn.password:
        env["PGPASSWORD"] = conn.password

    cmd = [
        "pg_dump",
        "-Fc",  # custom format, compatible with pg_restore
        "-h",
        conn.host,
        "-p",
        conn.port,
        "-U",
        conn.user,
        "-f",
        str(out_file),
        conn.db,
    ]
    print("[INFO] Running:", " ".join(cmd))
    run_cmd(cmd, env=env)
    print(f"[OK] PostgreSQL backup created: {out_file}")
    return out_file


def s3_upload(local_path: Path, bucket: str, prefix: Optional[str]) -> str:
    check_cmd_exists("aws")
    s3_uri = f"s3://{bucket}/" + (f"{prefix.strip('/')}/" if prefix else "") + local_path.name
    cmd = ["aws", "s3", "cp", str(local_path), s3_uri]
    print("[INFO] Uploading to S3:", s3_uri)
    run_cmd(cmd)
    print(f"[OK] Uploaded to {s3_uri}")
    return s3_uri


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backup PostgreSQL database")
    p.add_argument("--database-url", dest="database_url", default=None, help="Override DATABASE_URL")
    p.add_argument("--out", dest="out_dir", default=str(BACKUPS_DIR), help="Output directory for backups")
    p.add_argument("--s3-bucket", dest="s3_bucket", default=None, help="Optional S3 bucket to upload backup")
    p.add_argument("--s3-prefix", dest="s3_prefix", default=None, help="Optional S3 key prefix (folder)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    url = get_database_url(args.database_url)
    out_dir = Path(args.out_dir)

    # PostgreSQL only
    backup_path = backup_postgres(url, out_dir)

    if args.s3_bucket:
        s3_upload(backup_path, args.s3_bucket, args.s3_prefix)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[ERROR] Backup failed: {exc}", file=sys.stderr)
        sys.exit(1)
