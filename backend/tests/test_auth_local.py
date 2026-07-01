from __future__ import annotations

import os
import time

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.cookies import create_session_cookie_value, parse_session_cookie_value
from app.auth.passwords import hash_password, verify_password
from app.database import Base, get_db
from app.models import User
from app.routers.auth import router as auth_router


def test_password_hashing_round_trip():
    password_hash = hash_password("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", password_hash) is True
    assert verify_password("wrong password", password_hash) is False
    assert verify_password("", password_hash) is False
    assert verify_password("correct horse battery staple", "not-a-valid-hash") is False


def test_session_cookie_round_trip_tamper_and_expiry():
    cookie_value = create_session_cookie_value(user_id=42, ttl_seconds=60)

    assert parse_session_cookie_value(cookie_value) == 42
    assert parse_session_cookie_value(f"{cookie_value}x") is None

    expired_cookie = create_session_cookie_value(user_id=42, ttl_seconds=-1)
    time.sleep(1)
    assert parse_session_cookie_value(expired_cookie) is None


def _make_test_client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine, tables=[User.__table__])
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    with SessionLocal() as session:
        session.add(
            User(
                email="trusted@example.com",
                password_hash=hash_password("password123"),
                display_name="Trusted User",
                is_active=True,
            )
        )
        session.add(
            User(
                email="inactive@example.com",
                password_hash=hash_password("password123"),
                display_name="Inactive User",
                is_active=False,
            )
        )
        session.commit()

    app = FastAPI()
    app.include_router(auth_router)

    def override_get_db():
        with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), engine


def test_login_sets_cookie_and_me_returns_current_user():
    client, engine = _make_test_client()
    try:
        response = client.post(
            "/api/auth/login",
            json={"email": "TRUSTED@example.com", "password": "password123"},
        )

        assert response.status_code == 200
        assert "clerk_session=" in response.headers["set-cookie"]
        body = response.json()
        assert body["user"]["email"] == "trusted@example.com"
        assert body["user"]["display_name"] == "Trusted User"
        assert body["user"]["last_login_at"] is not None

        me_response = client.get("/api/auth/me")

        assert me_response.status_code == 200
        assert me_response.json()["email"] == "trusted@example.com"
    finally:
        engine.dispose()


def test_login_rejects_invalid_and_inactive_users():
    client, engine = _make_test_client()
    try:
        invalid_response = client.post(
            "/api/auth/login",
            json={"email": "trusted@example.com", "password": "wrong"},
        )
        inactive_response = client.post(
            "/api/auth/login",
            json={"email": "inactive@example.com", "password": "password123"},
        )

        assert invalid_response.status_code == 401
        assert inactive_response.status_code == 403
    finally:
        engine.dispose()


def test_logout_clears_cookie_and_me_requires_authentication():
    client, engine = _make_test_client()
    try:
        assert client.get("/api/auth/me").status_code == 401

        login_response = client.post(
            "/api/auth/login",
            json={"email": "trusted@example.com", "password": "password123"},
        )
        assert login_response.status_code == 200

        logout_response = client.post("/api/auth/logout")

        assert logout_response.status_code == 200
        assert logout_response.json() == {"success": True}
        assert "clerk_session=" in logout_response.headers["set-cookie"]
        assert client.get("/api/auth/me").status_code == 401
    finally:
        engine.dispose()
