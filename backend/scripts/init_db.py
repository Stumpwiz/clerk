#!/usr/bin/env python3
"""
Initialize the database for the Clerk backend.

Features:
- Creates all tables from SQLAlchemy models (create_all)
- Optionally runs Alembic migrations to upgrade to head
- Optional seed step to populate initial data

Usage examples (from backend/ or project root):

  # Create tables only (without Alembic)
  python backend/scripts/init_db.py --create --no-migrate

  # Run Alembic migrations only
  python backend/scripts/init_db.py --migrate

  # Do everything (create + migrate + seed)
  python backend/scripts/init_db.py --create --migrate --seed

Environment:
  - Reads DATABASE_URL via app.config (or oldEnv) and Alembic env.py.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError


def seed_initial_data() -> None:
    """Seed initial data if needed.

    This is a safe no-op placeholder. Extend with real seed logic if required.
    """
    # Example pattern (uncomment and adjust as your models exist):
    # from app.database import SessionLocal
    # from app.models import Body
    # with SessionLocal() as session:
    #     if session.query(Body).count() == 0:
    #         session.add(Body(name="Default Body"))
    #         session.commit()
    print("[init-db] Seed step: nothing to do (placeholder).")


def run_create_all(echo: bool = False) -> None:
    # Import models to ensure they are registered with Base before create_all
    # This relies on app.models.__init__ importing all model modules.
    from app import models  # noqa: F401  # import side-effects register models
    from app.database import Base, engine  # lazy import to ensure settings are loaded
    if echo:
        print("[init-db] Creating all tables using SQLAlchemy Base.metadata.create_all()…")
    Base.metadata.create_all(bind=engine)
    if echo:
        print("[init-db] create_all complete.")


def run_alembic_upgrade_head(echo: bool = False, ini_path: Optional[str] = None) -> None:
    if echo:
        print("[init-db] Running Alembic migrations: upgrade head…")
    from alembic import command
    from alembic.config import Config

    # Default to local alembic.ini (working directory is backend/ in Docker)
    ini = ini_path or "alembic.ini"
    cfg = Config(ini)
    # Let env.py resolve DATABASE_URL from the environment
    command.upgrade(cfg, "head")
    if echo:
        print("[init-db] Alembic upgrade complete.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Initialize database: create tables, migrate, and seed")
    p.add_argument("--create", action="store_true", help="Create all tables using SQLAlchemy Base.metadata.create_all()")
    p.add_argument("--migrate", dest="migrate", action="store_true", help="Run Alembic upgrade head")
    p.add_argument("--no-migrate", dest="migrate", action="store_false", help="Do not run Alembic migrations")
    p.add_argument("--seed", action="store_true", help="Seed initial data after creation/migration")
    p.add_argument("--echo", action="store_true", help="Verbose output")
    p.set_defaults(migrate=True)  # default behavior runs migrations
    return p.parse_args()


def main() -> int:
    args = parse_args()

    try:
        if args.create:
            run_create_all(echo=args.echo)

        if args.migrate:
            run_alembic_upgrade_head(echo=args.echo)

        if args.seed:
            seed_initial_data()

        if not any([args.create, args.migrate, args.seed]):
            # If no action specified, do a sensible default: migrations only
            run_alembic_upgrade_head(echo=True)

        print("[init-db] Done.")
        return 0
    except SQLAlchemyError as e:
        print("[init-db] SQLAlchemy error:", e)
        return 1
    except Exception as e:  # noqa: BLE001
        print("[init-db] Failed:", e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
