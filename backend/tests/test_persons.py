from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import require_authenticated_user
from app.database import get_db
from app.models import Person
from app.routers.persons import _is_duplicate_person_error, router as persons_router


class _PostgresDatabaseError(Exception):
    def __init__(self, constraint_name: str):
        self.diag = type("Diagnostics", (), {"constraint_name": constraint_name})()


def _make_test_client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Person.__table__.create(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    app = FastAPI()
    app.include_router(persons_router)

    def override_get_db():
        with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_authenticated_user] = lambda: object()
    return TestClient(app), engine


def test_create_duplicate_person_returns_conflict_with_useful_message():
    client, engine = _make_test_client()
    try:
        payload = {"first": "Ada", "last": "Lovelace"}

        first_response = client.post("/api/persons", json=payload)
        duplicate_response = client.post("/api/persons", json=payload)

        assert first_response.status_code == 201
        assert duplicate_response.status_code == 409
        assert duplicate_response.json() == {
            "detail": "A person with this first and last name already exists"
        }
    finally:
        engine.dispose()


def test_unrelated_integrity_error_is_not_treated_as_duplicate_person():
    exc = IntegrityError(
        "INSERT INTO other_table",
        {},
        Exception("FOREIGN KEY constraint failed"),
    )

    assert _is_duplicate_person_error(exc) is False


def test_only_named_postgres_person_constraint_is_treated_as_duplicate():
    duplicate = IntegrityError(
        "INSERT INTO person",
        {},
        _PostgresDatabaseError("uix_person_first_last"),
    )
    unrelated_unique = IntegrityError(
        "INSERT INTO person",
        {},
        _PostgresDatabaseError("some_other_unique_constraint"),
    )

    assert _is_duplicate_person_error(duplicate) is True
    assert _is_duplicate_person_error(unrelated_unique) is False
