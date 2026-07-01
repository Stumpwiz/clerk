"""
Pytest fixtures for database-backed tests using PostgreSQL (via Docker or env).

- Provides `postgres_url` from env (skips tests if not provided)
- Runs Alembic migrations against PostgreSQL before tests
- Provides a clean SQLAlchemy Session bound to PostgreSQL
- Provides a Docker-backed temporary PostgreSQL database for integration tests
"""

from __future__ import annotations

import os
import sys
import pathlib
import subprocess
from typing import Iterator

import pytest
import docker
from time import sleep
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session


def _ensure_backend_on_path() -> pathlib.Path:
    backend_dir = pathlib.Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    return backend_dir


_ensure_backend_on_path()


def _alembic_upgrade(url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    # Run alembic from backend directory to ensure config resolution
    backend_dir = _ensure_backend_on_path()
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(backend_dir / "alembic.ini"), "upgrade", "head"],
        cwd=str(backend_dir),
        check=True,
        env=env,
    )


@pytest.fixture(scope="session")
def postgres_url() -> str:
    url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not url or not url.startswith("postgresql"):
        pytest.skip("DATABASE_URL not set to PostgreSQL; skipping Postgres migration tests")
    return url


@pytest.fixture(scope="session")
def migrated_postgres(postgres_url: str) -> str:
    # Ensure alembic has created schema
    _alembic_upgrade(postgres_url)
    return postgres_url


@pytest.fixture()
def pg_session(migrated_postgres: str) -> Iterator[Session]:
    engine = create_engine(migrated_postgres, pool_pre_ping=True, future=True)
    # Clean tables between tests (respect FK dependencies)
    with engine.begin() as conn:
        # Delete order: term -> office -> person -> body; letters independent
        conn.execute(text("DELETE FROM term"))
        conn.execute(text("DELETE FROM office"))
        conn.execute(text("DELETE FROM person"))
        conn.execute(text("DELETE FROM body"))
        conn.execute(text("DELETE FROM letters"))
        conn.execute(text("DELETE FROM users"))
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    try:
        with SessionLocal() as s:
            yield s
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def postgres_test_db() -> Iterator[str]:
    """
    Spin up a temporary PostgreSQL container for testing.
    Uses Docker to create an isolated test database.
    """
    client = docker.from_env()

    # Start PostgreSQL container
    container = client.containers.run(
        "postgres:18.1-alpine",
        environment={
            "POSTGRES_USER": "test_user",
            "POSTGRES_PASSWORD": "test_password",
            "POSTGRES_DB": "test_clerk_db",
        },
        ports={"5432/tcp": None},  # Random host port
        detach=True,
        remove=True,
    )

    # Get the mapped port
    container.reload()
    port = container.ports["5432/tcp"][0]["HostPort"]
    db_url = f"postgresql://test_user:test_password@localhost:{port}/test_clerk_db"

    # Wait for PostgreSQL to be ready
    max_attempts = 30
    for _ in range(max_attempts):
        try:
            engine = create_engine(db_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            break
        except Exception:
            sleep(0.5)
    else:
        container.stop()
        raise RuntimeError("PostgreSQL container failed to start")

    try:
        yield db_url
    finally:
        # Cleanup
        container.stop()
