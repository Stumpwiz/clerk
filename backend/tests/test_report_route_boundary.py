"""Route regressions using synthetic authentication, without database access."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def route_client(monkeypatch):
    from pydantic_settings import DotEnvSettingsSource
    from sqlalchemy.engine import Engine

    # Never load local credentials or connect to a database for these tests.
    monkeypatch.setattr(DotEnvSettingsSource, "_read_env_files", lambda self: {})
    monkeypatch.setenv("CLERK_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    def forbid_connection(*args, **kwargs):
        pytest.fail("Route boundary tests must not open database connections")

    monkeypatch.setattr(Engine, "connect", forbid_connection)

    from app.config import settings
    monkeypatch.setattr(settings, "auth_secret_key", "synthetic-route-test-key")
    monkeypatch.setattr(settings, "session_cookie_secure", False)

    from app.database import get_db
    # Router imports construct PDF helpers; suppress only directory creation.
    with monkeypatch.context() as import_guard:
        import_guard.setattr(Path, "mkdir", lambda self, *a, **kw: None)
        from app.main import app
    from app.models import User

    user = User(
        id=42,
        email="route-test@example.invalid",
        display_name="Synthetic User",
        is_active=True,
        session_version=0,
    )

    class SyntheticSession:
        def get(self, model, identifier):
            assert model is User
            return user if identifier == user.id else None

        def query(self, *args, **kwargs):
            pytest.fail("These routes must not query resident data")

    def synthetic_db():
        yield SyntheticSession()

    monkeypatch.setitem(app.dependency_overrides, get_db, synthetic_db)
    # No lifespan/startup execution is needed to test routing.
    client = TestClient(app)
    try:
        yield client, app
    finally:
        client.close()


def authenticate(client):
    from app.auth.cookies import create_session_cookie_value
    from app.config import settings

    client.cookies.set(settings.session_cookie_name, create_session_cookie_value(42))
    # Prove this cookie passes the real authentication dependency.
    response = client.get("/api/reports")
    assert response.status_code == 200
    assert any(report["id"] == "long-roster" for report in response.json())


@pytest.mark.parametrize("authenticated", [False, True])
def test_removed_report_records_returns_404(route_client, authenticated):
    client, _ = route_client
    if authenticated:
        authenticate(client)

    response = client.get("/api/report-records")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_legitimate_report_routes_require_authentication(route_client):
    client, app = route_client
    paths = {
        route.path for route in app.routes
        if route.path.startswith("/api/reports") and "GET" in route.methods
    }
    assert {"/api/reports", "/api/reports/pdfs"} <= paths
    for path in sorted(paths):
        response = client.get(path.replace("{filename}", "synthetic.pdf"))
        assert response.status_code == 401, path
        assert response.json() == {"detail": "Authentication required"}, path


def test_authenticated_report_catalog_remains_available(route_client):
    client, _ = route_client
    authenticate(client)
