"""
Pytest fixtures for database-backed tests across SQLite and PostgreSQL.

- Provides `postgres_url` from env (skips tests if not provided)
- Runs Alembic migrations against PostgreSQL before tests
- Provides a clean SQLAlchemy Session bound to PostgreSQL
- Provides a temporary SQLite database URL and prepopulated schema/data
"""

from __future__ import annotations

import os
import sys
import pathlib
import subprocess
from typing import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session


def _ensure_backend_on_path() -> pathlib.Path:
    backend_dir = pathlib.Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    return backend_dir


def _alembic_upgrade(url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    # Run alembic from backend directory to ensure config resolution
    backend_dir = _ensure_backend_on_path()
    subprocess.run(
        ["alembic", "-c", str(backend_dir / "alembic.ini"), "upgrade", "head"],
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
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    try:
        with SessionLocal() as s:
            yield s
    finally:
        engine.dispose()


@pytest.fixture()
def sqlite_temp_db(tmp_path: pathlib.Path) -> str:
    # Create a temporary SQLite file URL
    sqlite_file = tmp_path / "source.sqlite"
    url = f"sqlite:///{sqlite_file}"

    # Create tables and minimal seed data using ORM metadata
    _ensure_backend_on_path()
    from app.database import Base
    import app.models  # ensure models imported
    engine = create_engine(url, connect_args={"check_same_thread": False})
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            # Seed some basic rows to migrate
            conn.execute(text("INSERT INTO body (name, mission, body_precedence) VALUES ('Housing Authority','Serve community',1.0)"))
            conn.execute(text("INSERT INTO office (title, office_precedence, office_body_id) VALUES ('Chair', 1.0, 1)"))
            conn.execute(text("INSERT INTO person (first,last,email,phone,apt) VALUES ('Ada','Lovelace','ada@example.com','555-0000',NULL)"))
            conn.execute(text('INSERT INTO term (termpersonid, termofficeid, start, "end", ordinal) VALUES (1,1,NULL,NULL, :ord)'), {"ord": "1st"})
            conn.execute(text("INSERT INTO letters (header, body) VALUES ('Welcome','Welcome to the community!')"))
    finally:
        engine.dispose()

    return url
