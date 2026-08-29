from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.routers import help


def _make_test_client(current_user):
    app = FastAPI()
    app.include_router(help.router)
    app.dependency_overrides[get_current_user] = lambda: current_user
    return TestClient(app)


def test_help_guide_requires_authentication():
    client = _make_test_client(current_user=None)

    response = client.get("/api/help/administrative-assistant-user-guide")

    assert response.status_code == 401


def test_help_guide_returns_packaged_pdf_for_authenticated_user():
    client = _make_test_client(current_user=object())

    response = client.get("/api/help/administrative-assistant-user-guide")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        'inline; filename="Administrative Assistant User Guide.pdf"'
    )
    assert response.content.startswith(b"%PDF-")
    assert response.content == help.GUIDE_PATH.read_bytes()
