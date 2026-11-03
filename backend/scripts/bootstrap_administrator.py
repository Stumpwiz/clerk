#!/usr/bin/env python3
"""One-time promotion of an explicitly identified existing active account.

Requires the administrator/session migrations and a separately authorized target
database. Never accepts a database URL or password on the command line.
"""

import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy import func, select, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class BootstrapRefused(Exception):
    """The one-time bootstrap preconditions or postcondition were not met."""


def bootstrap(session, user_id: int, *, dry_run: bool) -> None:
    """Use a fresh session; all checks and the sole update share one transaction."""
    from app.models import User

    if type(user_id) is not int or user_id <= 0:
        raise BootstrapRefused()
    with session.begin():
        dialect = session.get_bind().dialect.name
        if dialect == "postgresql":
            # Fresh snapshots after waiting for another bootstrap's table lock.
            session.connection(execution_options={"isolation_level": "READ COMMITTED"})
            session.execute(text("SET LOCAL lock_timeout = '5s'"))
            session.execute(text("SET LOCAL statement_timeout = '15s'"))
            # Also blocks ordinary concurrent inserts, updates and deletions.
            session.execute(text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))
        elif dialect == "sqlite":
            # Supports isolated synthetic tests with the same serialized checks.
            session.execute(text("BEGIN IMMEDIATE"))
        else:
            raise BootstrapRefused()

        matches = session.scalars(
            select(User.id).where(User.id == user_id, User.is_active.is_(True))
        ).all()
        administrators = select(func.count()).select_from(User).where(User.is_admin.is_(True))
        if len(matches) != 1 or session.scalar(administrators) != 0:
            raise BootstrapRefused()
        if dry_run:
            session.rollback()
            return

        # Explicit SQL avoids the model's updated_at onupdate default: only the
        # requested flag changes, with no password, session or timestamp updates.
        result = session.execute(text(
            "UPDATE users SET is_admin = true "
            "WHERE id = :user_id AND is_active = true AND is_admin = false"
        ), {"user_id": user_id})
        active_administrators = administrators.where(User.is_active.is_(True))
        if (result.rowcount != 1 or session.scalar(administrators) != 1
                or session.scalar(active_administrators) != 1):
            raise BootstrapRefused()
        # Successful context exit commits; any exception rolls back.


def positive_id(value):
    try:
        result = int(value)
        if result > 0:
            return result
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("Use a positive integer account ID.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Promote exactly one existing active user only if no administrator exists.",
        epilog="Examples: bootstrap_administrator.py --user-id 123 --dry-run; "
               "bootstrap_administrator.py --user-id 123 --apply",
    )
    parser.add_argument("--user-id", required=True, type=positive_id)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Check preconditions; do not change records.")
    mode.add_argument("--apply", action="store_true", help="Apply the one-time promotion and commit.")
    args = parser.parse_args(argv)

    # Suppress SQL/configuration diagnostics, including credential-bearing errors.
    # Imports are deferred so --help never loads configuration or opens a database.
    previous_logging_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        from app.database import SessionLocal

        with SessionLocal() as session:
            bootstrap(session, args.user_id, dry_run=args.dry_run)
    except BootstrapRefused:
        print("Bootstrap refused: preconditions or verification not satisfied.", file=sys.stderr)
        return 1
    except Exception:
        # A commit transport failure can leave an uncertain outcome. Never retry
        # automatically or print exception text/parameters/connection details.
        print("Bootstrap failed; outcome not confirmed. Stop and review before retrying.", file=sys.stderr)
        return 1
    finally:
        logging.disable(previous_logging_disable)
    print("Preconditions satisfied; no changes made." if args.dry_run else "Administrator bootstrap committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
