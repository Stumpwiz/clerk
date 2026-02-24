"""Alembic environment configuration.

This file configures Alembic to use the DATABASE_URL from the environment
and integrates with the application's SQLAlchemy models metadata.
"""

from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path
import sys

from sqlalchemy import engine_from_config, pool
from alembic import context

# Load .env if present
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass

# This is the Alembic Config object, which provides access to
# the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# If the ini lacks logging sections, fall back to basicConfig to avoid KeyError.
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    except Exception:
        import logging
        logging.basicConfig(level=logging.INFO)


def get_database_url() -> str:
    """Resolve DATABASE_URL with fallback to ini value.

    Prefer app.config.get_database_url() which can assemble the URL from
    POSTGRES_* parts (including POSTGRES_PASSWORD) when DATABASE_URL is not
    explicitly set. This helps local setups where credentials are provided as
    separate env vars.
    """
    try:
        # Reuse application logic for building the URL from env variables
        from app.config import get_database_url as app_get_db_url  # type: ignore

        url = app_get_db_url()
        if url:
            return url
    except Exception:
        pass

    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    # fallback to alembic.ini's sqlalchemy.url
    return config.get_main_option("sqlalchemy.url")


# Set the sqlalchemy.url in config dynamically from environment
config.set_main_option("sqlalchemy.url", get_database_url())

# Ensure the backend directory is on sys.path so `import app.*` works when running alembic
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import application's Base metadata and register all models for autogenerate support
from app.database import Base  # noqa: E402
# Ensure all model modules are imported so their tables are attached to Base.metadata
try:  # noqa: SIM105
    import app.models  # noqa: F401
except Exception:
    # If models fail to import, autogenerate will produce an empty migration
    # but we still allow Alembic to proceed for troubleshooting.
    pass

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.
    """

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    configuration = config.get_section(config.config_ini_section) or {}
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
