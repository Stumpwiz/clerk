#!/usr/bin/env python3
"""Fixed-scope recovery operations; no application settings, dotenv or INI files.

Each invocation performs ONE separately authorized operation. No automatic retry.
The password exists only in process memory and driver connection arguments.
"""

import argparse
import getpass
import logging
import os
from pathlib import Path
import sys
import warnings

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
import psycopg2
from sqlalchemy import Boolean, Integer, column, create_engine, table, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from bootstrap_administrator import bootstrap

HOST = "clerk-db.c4agslv7s5zu.us-east-1.rds.amazonaws.com"
DATABASE = "clerk_community_admin"
ROLE = "clerk_user"
CA = Path("/home/geo/.local/share/aws-rds/us-east-1-bundle.pem")
BASE = "92d6f8a1c430"
REVISIONS = ("c61d8e4a2b90", "d82f6a9b3104")
TARGET = REVISIONS[-1]
USER_ID = 1
USERS = table("users", column("id", Integer), column("is_active", Boolean),
              column("is_admin", Boolean))


class RecoveryRefused(Exception):
    """A fixed recovery precondition was not met."""


def prompt_password():
    # Refuse getpass's echoed-stdin fallback, including redirected invocations.
    with open("/dev/tty", "r+"):
        pass
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        password = getpass.getpass("Database password: ")
    if not password:
        raise RecoveryRefused()
    return password


def recovery_engine(password):
    if not password or not CA.is_file() or any(k.startswith("PG") for k in os.environ):
        raise RecoveryRefused()
    # No password in the URL, environment, Alembic config, or SQL parameters.
    # Explicit libpq parameters prevent localhost and saved-password fallback.
    def connect():
        return psycopg2.connect(
            host=HOST, port=5432, dbname=DATABASE, user=ROLE, password=password,
            sslmode="verify-full", sslrootcert=str(CA), passfile="/dev/null",
            connect_timeout=5, application_name="clerk-recovery",
            options="-c search_path=public -c lock_timeout=5000 "
                    "-c statement_timeout=30000 -c idle_in_transaction_session_timeout=60000",
        )
    return create_engine("postgresql+psycopg2://", creator=connect,
                         poolclass=NullPool, echo=False, hide_parameters=True)


def preflight(connection, revision):
    if connection.dialect.name != "postgresql":
        raise RecoveryRefused()
    identity = connection.execute(text(
        "SELECT current_database(), current_user, current_schema()"
    )).one()
    versions = connection.execute(text(
        "SELECT version_num FROM public.alembic_version"
    )).scalars().all()
    target = connection.execute(text(
        "SELECT id, is_active FROM public.users WHERE id = :id"
    ), {"id": USER_ID}).all()
    if (tuple(identity) != (DATABASE, ROLE, "public") or versions != [revision]
            or [tuple(row) for row in target] != [(USER_ID, True)]):
        raise RecoveryRefused()


def migrate(connection):
    # Use public Alembic APIs and the reviewed revision modules directly, without
    # env.py, application imports, autogeneration or arbitrary target selection.
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    scripts = ScriptDirectory.from_config(config)
    with connection.begin():
        preflight(connection, BASE)
        connection.execute(text(
            "LOCK TABLE public.alembic_version, public.users IN ACCESS EXCLUSIVE MODE"
        ))
        preflight(connection, BASE)  # Recheck after waiting for concurrent work.
        context = MigrationContext.configure(connection, opts={"version_table_schema": "public"})
        previous = BASE
        with Operations.context(context):
            for revision in REVISIONS:
                script = scripts.get_revision(revision)
                if script.revision != revision or script.down_revision != previous:
                    raise RecoveryRefused()
                script.module.upgrade()
                previous = revision
        context.stamp(scripts, TARGET)
        preflight(connection, TARGET)
        if connection.execute(text(
            "SELECT EXISTS (SELECT 1 FROM public.users "
            "WHERE is_admin IS DISTINCT FROM false OR session_version IS DISTINCT FROM 0)"
        )).scalar_one():
            raise RecoveryRefused()
        # Both DDL changes and the revision update commit together on exit.


def perform(engine, operation):
    if operation not in {"migrate", "bootstrap-dry-run", "bootstrap-apply"}:
        raise RecoveryRefused()
    with engine.connect() as connection:
        if operation == "migrate":
            migrate(connection)
        else:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                preflight(connection, TARGET)
            # Keep the SAME physical connection, with no transaction open, so
            # the existing bootstrap owns its transaction and table lock.
            with Session(bind=connection) as session:
                bootstrap(session, USER_ID, dry_run=operation == "bootstrap-dry-run",
                          user_table=USERS)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Fixed RDS recovery: two migrations or bootstrap user ID 1.",
        epilog="Examples: recovery_database.py migrate; recovery_database.py bootstrap-dry-run; "
               "recovery_database.py bootstrap-apply. Each requires separate authorization.",
    )
    parser.add_argument("operation", choices=("migrate", "bootstrap-dry-run", "bootstrap-apply"))
    args = parser.parse_args(argv)
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    engine = None
    stage = "connection setup"
    try:
        engine = recovery_engine(prompt_password())
        stage = args.operation
        perform(engine, args.operation)
    except (Exception, KeyboardInterrupt):
        # Never print exceptions: even driver failures may contain credentials.
        print(f"Recovery stopped during {stage}; outcome unconfirmed. "
              "Verify state read-only before any retry.", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()
        logging.disable(previous)
    print("Bootstrap preconditions satisfied; no changes made." if args.operation == "bootstrap-dry-run"
          else f"{args.operation} committed; perform read-only verification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
