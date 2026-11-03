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
RESET_IDS = (1, 13, 17)
USERS = table("users", column("id", Integer), column("is_active", Boolean),
              column("is_admin", Boolean))


class RecoveryRefused(Exception):
    """A fixed recovery precondition was not met."""


def prompt_password(prompt="Database password: "):
    # Refuse getpass's echoed-stdin fallback, including redirected invocations.
    # This is only an availability check. Update mode (r+) uses a seekable
    # BufferedRandom stream, which terminals do not support. getpass separately
    # opens the terminal for its hidden-input handling.
    with open("/dev/tty", "r"):
        pass
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        password = getpass.getpass(prompt)
    if not password:
        raise RecoveryRefused()
    return password


def validate_reset_passwords(passwords):
    if not isinstance(passwords, dict) or set(passwords) != set(RESET_IDS):
        raise RecoveryRefused()
    if any(not isinstance(value, str) or not 8 <= len(value) <= 1024
           or not value.strip() or not value.isprintable() for value in passwords.values()):
        raise RecoveryRefused()
    if len(set(passwords.values())) != len(RESET_IDS):
        raise RecoveryRefused()


def prompt_reset_passwords():
    """Collect and confirm all owner-saved passwords before opening a database."""
    passwords = {}
    for user_id in RESET_IDS:
        password = prompt_password(f"Saved replacement password for user ID {user_id}: ")
        confirmation = prompt_password(f"Confirm replacement password for user ID {user_id}: ")
        if password != confirmation:
            raise RecoveryRefused()
        passwords[user_id] = password
    validate_reset_passwords(passwords)
    return passwords


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


def reset_passwords(connection, passwords):
    """One-time atomic reset using passwords already retained by the owner."""
    validate_reset_passwords(passwords)
    # This module is pure hashing code: it does not import application settings.
    from app.auth.passwords import hash_password

    with connection.begin():
        preflight(connection, TARGET)
        connection.execute(text("LOCK TABLE public.users IN SHARE ROW EXCLUSIVE MODE"))
        rows = connection.execute(text(
            "SELECT id, is_active, is_admin, session_version FROM public.users "
            "WHERE id IN (1, 13, 17) ORDER BY id"
        )).all()
        expected = [(user_id, True, user_id == USER_ID, 0) for user_id in RESET_IDS]
        if ([tuple(row) for row in rows] != expected or connection.execute(text(
                "SELECT count(*) FROM public.users WHERE is_admin"
        )).scalar_one() != 1):
            raise RecoveryRefused()

        for user_id in RESET_IDS:
            result = connection.execute(text(
                "UPDATE public.users SET password_hash=:password_hash, "
                "session_version=session_version+1 WHERE id=:id AND session_version=0"
            ), {"id": user_id, "password_hash": hash_password(passwords[user_id])})
            if result.rowcount != 1:
                raise RecoveryRefused()
        after = connection.execute(text(
            "SELECT id, is_active, is_admin, session_version FROM public.users "
            "WHERE id IN (1, 13, 17) ORDER BY id"
        )).all()
        if ([tuple(row) for row in after] != [(*row[:3], 1) for row in expected]
                or connection.execute(text(
                    "SELECT count(*) FROM public.users WHERE is_admin"
                )).scalar_one() != 1):
            raise RecoveryRefused()


def perform(engine, operation, *, passwords=None):
    if operation not in {"migrate", "bootstrap-dry-run", "bootstrap-apply", "reset-passwords"}:
        raise RecoveryRefused()
    if operation == "reset-passwords":
        validate_reset_passwords(passwords)
    with engine.connect() as connection:
        if operation == "migrate":
            migrate(connection)
        elif operation == "reset-passwords":
            reset_passwords(connection, passwords)
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
        description="Fixed RDS recovery: migrations, administrator bootstrap, or three-user reset.",
        epilog="Examples: recovery_database.py migrate; recovery_database.py bootstrap-dry-run; "
               "recovery_database.py bootstrap-apply; recovery_database.py reset-passwords "
               "--confirm-passwords-saved. "
               "Each requires separate authorization. Reset requires session versions zero.",
    )
    parser.add_argument("operation", choices=("migrate", "bootstrap-dry-run", "bootstrap-apply", "reset-passwords"))
    parser.add_argument("--confirm-passwords-saved", action="store_true",
                        help="Owner confirms all three replacement passwords are already saved in Proton Pass.")
    args = parser.parse_args(argv)
    if args.operation == "reset-passwords":
        if not args.confirm_passwords_saved:
            parser.error("Reset requires --confirm-passwords-saved.")
    elif args.confirm_passwords_saved:
        parser.error("--confirm-passwords-saved applies only to reset-passwords.")
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    engine = None
    stage = "connection setup"
    try:
        passwords = None
        if args.operation == "reset-passwords":
            stage = "replacement password input"
            passwords = prompt_reset_passwords()
        stage = "connection setup"
        database_password = prompt_password()
        if passwords is not None and database_password in passwords.values():
            raise RecoveryRefused()
        engine = recovery_engine(database_password)
        stage = args.operation
        if passwords is None:
            perform(engine, args.operation)
        else:
            perform(engine, args.operation, passwords=passwords)
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
