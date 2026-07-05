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
from app.routers.users import router as users_router


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
    app.include_router(users_router)

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


def test_create_user_normalizes_email_and_stores_password_hash():
    client, engine = _make_test_client()
    try:
        login_response = client.post(
            "/api/auth/login",
            json={"email": "trusted@example.com", "password": "password123"},
        )
        assert login_response.status_code == 200

        response = client.post(
            "/api/users",
            json={
                "email": "NEW.USER@example.com",
                "display_name": "  New User  ",
                "password": "created-password",
                "is_active": True,
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "new.user@example.com"
        assert body["display_name"] == "New User"
        assert "password" not in body
        assert "password_hash" not in body

        with engine.connect() as connection:
            row = connection.exec_driver_sql(
                "SELECT email, display_name, password_hash, is_active FROM users WHERE email = ?",
                ("new.user@example.com",),
            ).one()

        assert row.email == "new.user@example.com"
        assert row.display_name == "New User"
        assert row.password_hash != "created-password"
        assert verify_password("created-password", row.password_hash) is True
        assert bool(row.is_active) is True

        new_login_response = client.post(
            "/api/auth/login",
            json={"email": "new.user@example.com", "password": "created-password"},
        )
        assert new_login_response.status_code == 200
    finally:
        engine.dispose()


def test_create_user_rejects_duplicate_email_case_insensitively():
    client, engine = _make_test_client()
    try:
        login_response = client.post(
            "/api/auth/login",
            json={"email": "trusted@example.com", "password": "password123"},
        )
        assert login_response.status_code == 200

        response = client.post(
            "/api/users",
            json={
                "email": "TRUSTED@example.com",
                "display_name": "Duplicate User",
                "password": "password123",
                "is_active": True,
            },
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "A user with this email already exists"
    finally:
        engine.dispose()


def test_create_user_validates_required_fields_and_authentication():
    client, engine = _make_test_client()
    try:
        unauthenticated_response = client.post(
            "/api/users",
            json={
                "email": "created@example.com",
                "display_name": "Created User",
                "password": "password123",
                "is_active": True,
            },
        )
        assert unauthenticated_response.status_code == 401

        login_response = client.post(
            "/api/auth/login",
            json={"email": "trusted@example.com", "password": "password123"},
        )
        assert login_response.status_code == 200

        missing_display_name_response = client.post(
            "/api/users",
            json={
                "email": "created@example.com",
                "display_name": "   ",
                "password": "password123",
                "is_active": True,
            },
        )
        missing_password_response = client.post(
            "/api/users",
            json={
                "email": "created@example.com",
                "display_name": "Created User",
                "password": "",
                "is_active": True,
            },
        )
        invalid_email_response = client.post(
            "/api/users",
            json={
                "email": "not-an-email",
                "display_name": "Created User",
                "password": "password123",
                "is_active": True,
            },
        )

        assert missing_display_name_response.status_code == 422
        assert missing_password_response.status_code == 422
        assert invalid_email_response.status_code == 422
    finally:
        engine.dispose()


def test_update_user_allows_display_name_and_active_only_preserving_auth_fields():
    client, engine = _make_test_client()
    try:
        login_response = client.post(
            "/api/auth/login",
            json={"email": "trusted@example.com", "password": "password123"},
        )
        assert login_response.status_code == 200

        response = client.put(
            "/api/users/1",
            json={"display_name": "  Updated Trusted  ", "is_active": True},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "trusted@example.com"
        assert body["display_name"] == "Updated Trusted"
        assert body["is_active"] is True

        with engine.connect() as connection:
            row = connection.exec_driver_sql(
                "SELECT email, display_name, password_hash FROM users WHERE id = ?",
                (1,),
            ).one()

        assert row.email == "trusted@example.com"
        assert row.display_name == "Updated Trusted"
        assert verify_password("password123", row.password_hash) is True

        existing_login_response = client.post(
            "/api/auth/login",
            json={"email": "trusted@example.com", "password": "password123"},
        )
        assert existing_login_response.status_code == 200
    finally:
        engine.dispose()


def test_update_user_rejects_blank_display_name_unknown_user_and_forbidden_fields():
    client, engine = _make_test_client()
    try:
        login_response = client.post(
            "/api/auth/login",
            json={"email": "trusted@example.com", "password": "password123"},
        )
        assert login_response.status_code == 200

        blank_response = client.put(
            "/api/users/1",
            json={"display_name": "   ", "is_active": True},
        )
        missing_response = client.put(
            "/api/users/999",
            json={"display_name": "Missing User", "is_active": True},
        )
        forbidden_response = client.put(
            "/api/users/1",
            json={
                "email": "changed@example.com",
                "display_name": "Changed User",
                "password": "changed-password",
                "is_active": True,
            },
        )

        assert blank_response.status_code == 422
        assert missing_response.status_code == 404
        assert forbidden_response.status_code == 422

        with engine.connect() as connection:
            row = connection.exec_driver_sql(
                "SELECT email, display_name, password_hash FROM users WHERE id = ?",
                (1,),
            ).one()

        assert row.email == "trusted@example.com"
        assert row.display_name == "Trusted User"
        assert verify_password("password123", row.password_hash) is True
    finally:
        engine.dispose()


def test_update_user_active_flag_controls_login():
    client, engine = _make_test_client()
    try:
        login_response = client.post(
            "/api/auth/login",
            json={"email": "trusted@example.com", "password": "password123"},
        )
        assert login_response.status_code == 200

        create_response = client.post(
            "/api/users",
            json={
                "email": "controlled@example.com",
                "display_name": "Controlled User",
                "password": "controlled-password",
                "is_active": True,
            },
        )
        assert create_response.status_code == 201
        controlled_user_id = create_response.json()["id"]

        deactivate_response = client.put(
            f"/api/users/{controlled_user_id}",
            json={"display_name": "Controlled User", "is_active": False},
        )
        inactive_login_response = client.post(
            "/api/auth/login",
            json={"email": "controlled@example.com", "password": "controlled-password"},
        )
        existing_active_login_response = client.post(
            "/api/auth/login",
            json={"email": "trusted@example.com", "password": "password123"},
        )

        assert deactivate_response.status_code == 200
        assert deactivate_response.json()["is_active"] is False
        assert inactive_login_response.status_code == 403
        assert existing_active_login_response.status_code == 200
    finally:
        engine.dispose()
