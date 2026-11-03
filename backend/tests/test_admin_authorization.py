"""Two-role authorization using only synthetic, in-memory SQLite users."""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.config import settings
from app.auth.cookies import create_session_cookie_value
from test_auth_local import _make_test_client


@pytest.fixture
def account_client():
    client, engine = _make_test_client()
    try:
        yield client, engine
    finally:
        client.close()
        engine.dispose()


def sign_in(client, user_id=1):
    client.cookies.set(settings.session_cookie_name, create_session_cookie_value(user_id))


OPERATIONS = [
    ("GET", "/api/users/list", None),
    ("POST", "/api/users", {"email": "new@example.com", "display_name": "New", "password": "password123"}),
    ("PUT", "/api/users/2", {"display_name": "Changed", "is_active": True}),
    ("POST", "/api/users/2/reset-password", {"new_password": "replacement123"}),
    ("DELETE", "/api/users/2", None),
]


@pytest.mark.parametrize("method,path,body", OPERATIONS)
@pytest.mark.parametrize("identity,expected", [("anonymous", 401), ("invalid", 401), ("ordinary", 403)])
def test_account_operations_deny_without_admin(account_client, method, path, body, identity, expected):
    client, engine = account_client
    if identity == "ordinary":
        with engine.begin() as connection:
            connection.exec_driver_sql("UPDATE users SET is_admin = 0 WHERE id = 1")
        sign_in(client)
    elif identity == "invalid":
        client.cookies.set(settings.session_cookie_name, "invalid-cookie")
    with engine.connect() as connection:
        before = connection.exec_driver_sql("SELECT * FROM users ORDER BY id").all()
    response = client.request(method, path, json=body)
    assert response.status_code == expected
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT * FROM users ORDER BY id").all() == before


@pytest.mark.parametrize("method,path,body", OPERATIONS)
def test_administrator_account_operations_permitted(account_client, method, path, body):
    client, engine = account_client
    sign_in(client)
    response = client.request(method, path, json=body)
    assert response.status_code == {"POST": 201 if path == "/api/users" else 200, "GET": 200, "PUT": 200, "DELETE": 204}[method]
    if path == "/api/users":
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT is_admin FROM users WHERE id = ?", (response.json()["id"],)).scalar_one() == 0


@pytest.mark.parametrize("field,value", [("is_admin", True), ("role", "administrator")])
@pytest.mark.parametrize("method,path,body", [OPERATIONS[1], OPERATIONS[2]])
def test_role_fields_rejected_even_for_administrator(account_client, field, value, method, path, body):
    client, engine = account_client
    sign_in(client)
    response = client.request(method, path, json={**body, field: value})
    assert response.status_code == 422
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM users").scalar_one() == 2
        assert connection.exec_driver_sql("SELECT is_admin FROM users WHERE id = 2").scalar_one() == 0


@pytest.mark.parametrize("active", [False, True])
def test_administrator_cannot_be_deactivated_or_deleted(account_client, active):
    client, engine = account_client
    with engine.begin() as connection:
        connection.exec_driver_sql("UPDATE users SET is_admin = 1, is_active = ? WHERE id = 2", (active,))
    sign_in(client)
    assert client.put("/api/users/2", json={"display_name": "Changed", "is_active": False}).status_code == 403
    assert client.delete("/api/users/2").status_code == 403
    with engine.connect() as connection:
        row = connection.exec_driver_sql("SELECT display_name, is_active, is_admin FROM users WHERE id = 2").one()
        assert tuple(row) == ("Inactive User", active, True)
    assert client.put("/api/users/1", json={"display_name": "Changed", "is_active": False}).status_code == 403
    assert client.delete("/api/users/1").status_code == 403


def test_database_role_changes_apply_to_existing_cookie(account_client):
    client, engine = account_client
    sign_in(client)
    cookie = client.cookies.get(settings.session_cookie_name)
    for is_admin, expected in [(True, 200), (False, 403), (True, 200)]:
        with engine.begin() as connection:
            connection.exec_driver_sql("UPDATE users SET is_admin = ? WHERE id = 1", (is_admin,))
        assert client.get("/api/users/list").status_code == expected
        assert client.get("/api/auth/me").json()["is_admin"] is is_admin
        assert client.cookies.get(settings.session_cookie_name) == cookie
    with engine.begin() as connection:
        connection.exec_driver_sql("UPDATE users SET is_active = 0 WHERE id = 1")
    assert client.get("/api/users/list").status_code == 401


@pytest.mark.parametrize("is_admin", [False, True])
def test_both_roles_keep_login_and_self_service_password_change(is_admin):
    client, engine = _make_test_client(is_admin=is_admin)
    try:
        response = client.post("/api/auth/login", json={"email": "trusted@example.com", "password": "password123"})
        assert response.status_code == 200
        assert response.json()["user"]["is_admin"] is is_admin
        assert client.get("/api/auth/me").json()["is_admin"] is is_admin
        assert client.post("/api/auth/change-password", json={"current_password": "password123", "new_password": "replacement123", "confirm_password": "replacement123"}).status_code == 200
    finally:
        client.close()
        engine.dispose()


def test_additive_migration_preserves_users_and_defaults_false():
    migration_path = Path(__file__).parents[1] / "alembic/versions/c61d8e4a2b90_add_user_is_admin.py"
    spec = importlib.util.spec_from_file_location("admin_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "92d6f8a1c430"
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL, password_hash TEXT NOT NULL, display_name TEXT NOT NULL, is_active BOOLEAN NOT NULL)")
            connection.exec_driver_sql("INSERT INTO users VALUES (1, 'one@example.invalid', 'synthetic-hash-1', 'One', 1), (2, 'two@example.invalid', 'synthetic-hash-2', 'Two', 0)")
            before = connection.exec_driver_sql("SELECT * FROM users ORDER BY id").all()
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            after = connection.exec_driver_sql("SELECT id, email, password_hash, display_name, is_active FROM users ORDER BY id").all()
            assert after == before
            assert connection.exec_driver_sql("SELECT is_admin FROM users ORDER BY id").scalars().all() == [0, 0]
            column = next(c for c in sa.inspect(connection).get_columns("users") if c["name"] == "is_admin")
            assert column["nullable"] is False
            connection.exec_driver_sql("INSERT INTO users (id,email,password_hash,display_name,is_active) VALUES (3,'three@example.invalid','synthetic','Three',1)")
            assert connection.exec_driver_sql("SELECT is_admin FROM users WHERE id=3").scalar_one() == 0
    finally:
        engine.dispose()


def test_ordinary_user_retains_report_roster_and_letter_access(monkeypatch):
    from app.models import GeneratedLetter, ReportRecord
    from app.database import Base
    with monkeypatch.context() as guard:
        guard.setattr(Path, "mkdir", lambda *args, **kwargs: None)
        from app.routers import reports, letters
    client, engine = _make_test_client(is_admin=False)
    client.app.include_router(reports.router)
    client.app.include_router(letters.router)
    Base.metadata.create_all(engine, tables=[ReportRecord.__table__, GeneratedLetter.__table__])
    try:
        paths = ["/api/reports", "/api/reports/vacancies/data", "/api/letters/pdfs"]
        for path in paths:
            assert client.get(path).status_code == 401
        sign_in(client)
        for path in paths:
            assert client.get(path).status_code == 200
    finally:
        client.close()
        engine.dispose()
