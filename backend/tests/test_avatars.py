"""Avatar behavior against an explicitly disposable PostgreSQL database."""
import asyncio
from io import BytesIO

import pytest
from fastapi import FastAPI
from starlette.exceptions import HTTPException
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.auth.cookies import create_session_cookie_value
from app.auth.origin import configure_origin_protection
from app.avatars import MAX_UPLOAD_BYTES, normalize_avatar
from app.database import get_db
from app.models import User
from app.routers import avatars, users

ORIGIN = "https://clerk.mrrc.online"


def picture(fmt="PNG", size=(320, 280), **kwargs):
    output = BytesIO()
    Image.new("RGB", size, "red").save(output, format=fmt, **kwargs)
    return output.getvalue()


@pytest.fixture
def context(pg_session):
    owner = User(email="owner@example.com", display_name="Owner", password_hash="unused")
    other = User(email="other@example.com", display_name="Other", password_hash="unused")
    admin = User(email="admin@example.com", display_name="Admin", password_hash="unused", is_admin=True)
    pg_session.add_all([owner, other, admin])
    pg_session.commit()
    app = FastAPI()
    app.include_router(avatars.router)
    app.include_router(users.router)
    configure_origin_protection(app, [ORIGIN])
    app.dependency_overrides[get_db] = lambda: pg_session
    client = TestClient(app, raise_server_exceptions=False)
    client.headers["origin"] = ORIGIN
    client.cookies.set("clerk_session", create_session_cookie_value(owner.id))
    return client, pg_session, owner.id, other.id, admin.id


def upload(client, data=None):
    return client.put("/api/auth/me/avatar", content=picture() if data is None else data,
                      headers={"content-type": "application/octet-stream"})


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_formats_persistence_deferred_and_replacement(context, fmt):
    client, db, owner, _, _ = context
    response = upload(client, picture(fmt))
    assert response.status_code == 200
    path = response.json()["avatar_path"]
    assert "avatar_bytes" not in response.json()
    delivered = client.get(path)
    assert delivered.status_code == 200
    assert delivered.headers["cache-control"] == "private, no-store"
    assert delivered.headers["x-content-type-options"] == "nosniff"
    with Image.open(BytesIO(delivered.content)) as image:
        assert image.format == "PNG" and image.size == (256, 256)
    with Session(db.bind) as fresh:
        persisted = fresh.get(User, owner)
        assert "avatar_bytes" in inspect(persisted).unloaded
        assert persisted.avatar_bytes == delivered.content
    new_path = upload(client, picture("PNG", (100, 200))).json()["avatar_path"]
    assert new_path != path
    assert client.get(path).status_code == 404
    assert client.get(new_path).status_code == 200
    for _ in range(2):
        assert client.delete("/api/auth/me/avatar").json()["avatar_path"] is None
    assert client.get(new_path).status_code == 404
    assert db.get(User, owner).avatar_bytes is None


@pytest.mark.parametrize("data,status", [
    (b"", 415), (b"not an image", 415), (b"<svg/>", 415),
    (picture("GIF"), 415), (picture()[:40], 415),
    (b"x" * (MAX_UPLOAD_BYTES + 1), 413),
    (picture(size=(4001, 4000)), 413),
])
def test_rejection_preserves_previous(context, data, status):
    client, db, owner, _, _ = context
    previous = upload(client).json()["avatar_path"]
    before = db.get(User, owner).avatar_bytes
    assert upload(client, data).status_code == status
    assert db.get(User, owner).avatar_path == previous
    assert db.get(User, owner).avatar_bytes == before


@pytest.mark.parametrize("fmt", ["PNG", "WEBP"])
def test_animation_rejected(fmt):
    output = BytesIO()
    Image.new("RGB", (10, 10), "red").save(
        output, format=fmt, save_all=True,
        append_images=[Image.new("RGB", (10, 10), "blue")], duration=100, loop=0,
    )
    with pytest.raises(HTTPException) as exc:
        normalize_avatar(output.getvalue())
    assert exc.value.status_code == 415


def test_metadata_orientation_and_center_crop():
    source = Image.new("RGB", (600, 300), "green")
    source.paste("red", (0, 0, 150, 300))
    source.paste("blue", (450, 0, 600, 300))
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = "private author"
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("secret", "private")
    output = BytesIO()
    source.save(output, format="PNG", exif=exif, pnginfo=metadata)
    with Image.open(BytesIO(normalize_avatar(output.getvalue()))) as result:
        assert result.getexif() == {}
        assert not result.info
        assert result.getpixel((128, 128))[:3] == (0, 128, 0)
        assert result.getpixel((128, 10))[:3] == (0, 128, 0)


@pytest.mark.parametrize("state", ["missing", "inactive", "stale", "tampered"])
def test_authentication(context, state):
    client, db, owner, _, _ = context
    path = upload(client).json()["avatar_path"]
    if state == "missing":
        client.cookies.clear()
    elif state == "tampered":
        client.cookies.set("clerk_session", "invalid")
    else:
        user = db.get(User, owner)
        if state == "inactive":
            user.is_active = False
        else:
            user.session_version += 1
        db.commit()
    assert upload(client).status_code == 401
    assert client.delete("/api/auth/me/avatar").status_code == 401
    assert client.get(path).status_code == 401


def test_authorization_and_account_deletion(context):
    client, db, owner, other, admin = context
    path = upload(client).json()["avatar_path"]
    client.cookies.set("clerk_session", create_session_cookie_value(other))
    assert client.get(path).status_code == 403
    own_path = upload(client).json()["avatar_path"]
    assert f"/{other}/" in own_path
    assert db.get(User, owner).avatar_path == path
    client.cookies.set("clerk_session", create_session_cookie_value(admin))
    assert client.get(path).status_code == 200
    db.get(User, owner).is_active = False
    db.commit()
    assert client.delete(f"/api/users/{owner}").status_code == 204
    assert db.scalar(select(User.avatar_bytes).where(User.id == owner)) is None
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("origin", [None, "https://evil.example"])
def test_origin(context, origin):
    client, _, _, _, _ = context
    client.headers.pop("origin")
    if origin:
        client.headers["origin"] = origin
    assert upload(client).status_code == 403
    assert client.delete("/api/auth/me/avatar").status_code == 403


@pytest.mark.parametrize("method", ["upload", "remove"])
def test_commit_failure_rolls_back(context, monkeypatch, method):
    client, db, owner, _, _ = context
    path = upload(client).json()["avatar_path"]
    before = db.get(User, owner).avatar_bytes

    def fail_commit():
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    response = upload(client) if method == "upload" else client.delete("/api/auth/me/avatar")
    assert response.status_code == 500
    with Session(db.bind) as fresh:
        persisted = fresh.get(User, owner)
        assert persisted.avatar_path == path
        assert persisted.avatar_bytes == before


def test_stream_limit_without_content_length_stops_receiving():
    received = 0

    async def receive():
        nonlocal received
        received += 1
        return {"type": "http.request", "body": b"x" * 1024 * 1024, "more_body": True}

    request = Request({"type": "http", "headers": []}, receive)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(avatars.bounded_image(request))
    assert exc.value.status_code == 413
    assert received == 3


def test_orientation_rotates_pixels():
    source = Image.new("RGB", (256, 256), "red")
    source.paste("blue", (128, 0, 256, 256))
    exif = Image.Exif()
    exif[274] = 6
    output = BytesIO()
    source.save(output, format="PNG", exif=exif)
    with Image.open(BytesIO(normalize_avatar(output.getvalue()))) as result:
        assert result.getpixel((128, 30))[:3] == (255, 0, 0)
        assert result.getpixel((128, 220))[:3] == (0, 0, 255)


def test_credentials_cors_and_untrusted_mime(context):
    client, _, _, _, _ = context
    response = client.put("/api/auth/me/avatar", content=picture(),
                          headers={"content-type": "text/plain"})
    assert response.status_code == 200
    image = client.get(response.json()["avatar_path"])
    assert image.headers["access-control-allow-origin"] == ORIGIN
    assert image.headers["access-control-allow-credentials"] == "true"
    assert image.headers["content-type"] == "image/png"


def test_exact_upload_limit_and_false_content_length():
    async def consume(length):
        messages = iter([
            {"type": "http.request", "body": b"x" * MAX_UPLOAD_BYTES, "more_body": True},
            {"type": "http.request", "body": b"x", "more_body": False},
        ])

        async def receive():
            return next(messages)

        await avatars.bounded_image(Request(
            {"type": "http", "headers": [(b"content-length", length)]}, receive,
        ))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(consume(b"1"))
    assert exc.value.status_code == 413

    async def exact():
        async def receive():
            return {"type": "http.request", "body": b"x" * MAX_UPLOAD_BYTES, "more_body": False}
        return await avatars.bounded_image(Request({"type": "http", "headers": []}, receive))

    assert len(asyncio.run(exact())) == MAX_UPLOAD_BYTES


def test_additive_migration_preserves_existing_user(pg_session):
    from pathlib import Path
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text

    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    migration = ScriptDirectory.from_config(config).get_revision("e93a7b2c4105").module
    assert migration.down_revision == "d82f6a9b3104"
    # Transactional, isolated schema: never downgrade the test application's table.
    with pg_session.bind.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("CREATE SCHEMA avatar_migration_test"))
            connection.execute(text("SET LOCAL search_path TO avatar_migration_test"))
            connection.execute(text("CREATE TABLE users (id integer PRIMARY KEY, avatar_path text)"))
            connection.execute(text("INSERT INTO users VALUES (1, '/existing.png')"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            assert connection.execute(text(
                "SELECT id, avatar_path, avatar_bytes FROM users"
            )).one() == (1, "/existing.png", None)
        finally:
            transaction.rollback()


def test_corrupt_png_checksum_preserves_previous_avatar(context):
    client, db, owner, _, _ = context
    previous = upload(client).json()["avatar_path"]
    before = db.get(User, owner).avatar_bytes
    corrupt = bytearray(picture())
    position = corrupt.index(b"IDAT")
    length = int.from_bytes(corrupt[position - 4:position], "big")
    corrupt[position + 4 + length] ^= 1
    assert upload(client, bytes(corrupt)).status_code == 415
    assert db.get(User, owner).avatar_path == previous
    assert db.get(User, owner).avatar_bytes == before
