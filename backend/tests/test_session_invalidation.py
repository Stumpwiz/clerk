"""Session revocation with synthetic SQLite users; PostgreSQL DDL is offline."""
import io
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.auth.cookies import _b64encode, _signature, create_session_cookie_value
from app.models import User
from app.routers.users import reset_user_password, UserPasswordResetRequest
from test_auth_local import _make_test_client


@pytest.fixture
def accounts():
    client, engine = _make_test_client()
    with engine.begin() as conn:
        conn.execute(sa.update(User).where(User.id == 2).values(is_active=True))
    yield client, engine
    client.close()
    engine.dispose()


def use_cookie(client, cookie):
    client.cookies.clear()
    client.cookies.set('clerk_session', cookie)


@pytest.mark.parametrize('admin_reset', [False, True])
def test_old_cookie_rejected_and_unrelated_cookie_survives(accounts, admin_reset):
    client, engine = accounts
    old = create_session_cookie_value(2)
    unrelated = create_session_cookie_value(1)
    use_cookie(client, unrelated if admin_reset else old)
    if admin_reset:
        response = client.post('/api/users/2/reset-password', json={'new_password': 'replacement123'})
    else:
        response = client.post('/api/auth/change-password', json={
            'current_password': 'password123', 'new_password': 'replacement123',
            'confirm_password': 'replacement123'})
        assert 'Max-Age=0' in response.headers['set-cookie']
        assert client.get('/api/auth/me').status_code == 401
    assert response.status_code == 200
    use_cookie(client, old)
    assert client.get('/api/auth/me').status_code == 401
    use_cookie(client, unrelated)
    assert client.get('/api/auth/me').status_code == 200
    assert client.post('/api/auth/login', json={'email': 'inactive@example.com', 'password': 'password123'}).status_code == 401
    assert client.post('/api/auth/login', json={'email': 'inactive@example.com', 'password': 'replacement123'}).status_code == 200
    assert client.get('/api/auth/me').status_code == 200
    with engine.connect() as conn:
        assert conn.execute(sa.select(User.session_version).where(User.id == 2)).scalar_one() == 1


@pytest.mark.parametrize('version', [None, True, False, '0', 0.0, -1, [], {}, 1])
def test_invalid_versions(accounts, version):
    client, _ = accounts
    payload = {'sub': 1, 'exp': 4102444800, 'session_version': version}
    encoded = _b64encode(json.dumps(payload).encode())
    use_cookie(client, encoded + '.' + _signature(encoded))
    assert client.get('/api/auth/me').status_code == 401


def test_legacy_cookie_rejected(accounts):
    client, _ = accounts
    encoded = _b64encode(json.dumps({'sub': 1, 'exp': 4102444800}).encode())
    use_cookie(client, encoded + '.' + _signature(encoded))
    assert client.get('/api/auth/me').status_code == 401


@pytest.mark.parametrize('admin_reset', [False, True])
def test_failed_change_preserves_hash_and_version(accounts, admin_reset):
    client, engine = accounts
    use_cookie(client, create_session_cookie_value(1))
    with engine.connect() as conn:
        before = conn.execute(sa.select(User.password_hash, User.session_version).where(User.id == 1)).one()
    response = client.post('/api/users/1/reset-password' if admin_reset else '/api/auth/change-password',
        json={'new_password': 'short'} if admin_reset else {
            'current_password': 'wrong', 'new_password': 'replacement123', 'confirm_password': 'replacement123'})
    assert response.status_code == 400
    with engine.connect() as conn:
        assert conn.execute(sa.select(User.password_hash, User.session_version).where(User.id == 1)).one() == before
    assert client.get('/api/auth/me').status_code == 200


def test_concurrent_resets_do_not_lose_increments(tmp_path):
    engine = sa.create_engine('sqlite:///' + str(tmp_path / 'synthetic.db'))
    User.__table__.create(engine)
    with Session(engine) as db:
        db.add(User(id=1, email='synthetic@example.com', display_name='Synthetic', password_hash='unused'))
        db.commit()
    barrier = Barrier(2)
    def reset():
        with Session(engine, expire_on_commit=False) as db:
            stale = db.get(User, 1)
            db.commit()  # Both identity maps retain version zero, without a read lock.
            barrier.wait(timeout=10)
            reset_user_password(1, UserPasswordResetRequest(new_password='replacement123'), db)
            return stale.id
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert list(pool.map(lambda _: reset(), range(2))) == [1, 1]
        with engine.connect() as conn:
            assert conn.execute(sa.select(User.session_version)).scalar_one() == 2
    finally:
        engine.dispose()


def test_migration_preserves_users_and_postgresql_ddl():
    backend = Path(__file__).resolve().parents[1]
    config = Config()
    config.set_main_option('script_location', str(backend / 'alembic'))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ['d82f6a9b3104']
    migration = scripts.get_revision('head').module
    assert migration.down_revision == 'c61d8e4a2b90'
    output = io.StringIO()
    context = MigrationContext.configure(dialect_name='postgresql', opts={'as_sql': True, 'output_buffer': output})
    with Operations.context(context):
        migration.upgrade()
    ddl = output.getvalue()
    assert "ALTER TABLE users ADD COLUMN session_version INTEGER DEFAULT '0' NOT NULL" in ddl
    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL)')
        conn.exec_driver_sql("INSERT INTO users VALUES (1, 'synthetic@example.com')")
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
        assert conn.exec_driver_sql('SELECT * FROM users').one() == (1, 'synthetic@example.com', 0)
        conn.exec_driver_sql("INSERT INTO users (id, email) VALUES (2, 'new@example.com')")
        assert conn.exec_driver_sql('SELECT session_version FROM users WHERE id=2').scalar_one() == 0
    engine.dispose()


def test_reset_during_login_does_not_issue_current_version(accounts, monkeypatch):
    from app.routers import auth
    client, engine = accounts
    original_verify = auth.verify_password

    def verify_then_reset(password, password_hash):
        valid = original_verify(password, password_hash)
        with engine.begin() as conn:
            conn.execute(sa.update(User).where(User.id == 1).values(
                password_hash='reset-hash', session_version=User.session_version + 1))
        return valid

    monkeypatch.setattr(auth, 'verify_password', verify_then_reset)
    assert client.post('/api/auth/login', json={
        'email': 'trusted@example.com', 'password': 'password123'}).status_code == 200
    assert client.get('/api/auth/me').status_code == 401
