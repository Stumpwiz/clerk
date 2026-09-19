"""Deletion policy and PostgreSQL concurrency tests."""
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import time

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth.cookies import create_session_cookie_value
from app.database import get_db
from app.models import User
from app.routers.users import router, delete_user


@pytest.fixture
def users(pg_session):
    caller = User(email='caller@example.com', display_name='Caller', password_hash='unused', is_active=True)
    target = User(email='target@example.com', display_name='Target', password_hash='unused', is_active=False)
    pg_session.add_all([caller, target]); pg_session.commit()
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: pg_session
    client = TestClient(app)
    client.cookies.set('clerk_session', create_session_cookie_value(caller.id))
    return client, pg_session, caller.id, target.id


def test_delete_inactive_other_returns_204(users):
    client, db, caller_id, target_id = users
    response = client.delete(f'/api/users/{target_id}')
    assert response.status_code == 204 and response.content == b''
    assert db.get(User, target_id) is None
    assert db.get(User, caller_id) is not None


def test_active_other_returns_409(users):
    client, db, _, target_id = users
    db.get(User, target_id).is_active = True; db.commit()
    response = client.delete(f'/api/users/{target_id}')
    assert response.status_code == 409
    assert 'first be made inactive' in response.json()['detail']
    assert db.get(User, target_id).is_active


def test_self_returns_403(users):
    client, db, caller_id, _ = users
    response = client.delete(f'/api/users/{caller_id}')
    assert response.status_code == 403
    assert 'own account' in response.json()['detail']
    assert db.get(User, caller_id) is not None


def test_self_guard_is_independent_of_active_flag(users):
    _, db, caller_id, _ = users
    caller = db.get(User, caller_id)
    caller.is_active = False
    # A normal inactive request is rejected by auth; also exercise the explicit
    # self guard with an already-resolved caller to ensure it is independent.
    with pytest.raises(HTTPException) as error:
        delete_user(caller_id, caller, db)
    assert error.value.status_code == 403
    db.rollback()


def test_missing_target_returns_404(users):
    client, _, _, _ = users
    assert client.delete('/api/users/2147483647').status_code == 404


@pytest.mark.parametrize('inactive', [False, True])
def test_unauthenticated_or_inactive_caller(users, inactive):
    client, db, caller_id, target_id = users
    if inactive:
        db.get(User, caller_id).is_active = False; db.commit()
    else:
        client.cookies.clear()
    assert client.delete(f'/api/users/{target_id}').status_code == 401
    assert db.get(User, target_id) is not None


def test_stale_identity_map_is_refreshed(users):
    client, db, _, target_id = users
    stale = db.get(User, target_id)
    assert not stale.is_active
    with Session(db.bind) as other:
        other.get(User, target_id).is_active = True; other.commit()
    response = client.delete(f'/api/users/{target_id}')
    assert response.status_code == 409
    assert stale.is_active


def test_concurrent_reactivation_wins_before_delete(users):
    _, db, caller_id, target_id = users
    engine = db.bind
    db.rollback()
    pids = Queue()

    def attempt_delete():
        with Session(engine) as deleting:
            caller = deleting.get(User, caller_id)
            pids.put(deleting.scalar(text('select pg_backend_pid()')))
            try:
                delete_user(target_id, caller, deleting)
            except HTTPException as exc:
                return exc.status_code

    with Session(engine) as reactivating, ThreadPoolExecutor(max_workers=1) as pool:
        reactivating.get(User, target_id).is_active = True
        reactivating.flush()  # UPDATE holds the row lock until commit.
        future = pool.submit(attempt_delete)
        try:
            pid = pids.get(timeout=5)
            deadline = time.monotonic() + 5
            with engine.connect() as observing:
                while time.monotonic() < deadline:
                    blocked = observing.scalar(text('select cardinality(pg_blocking_pids(:pid))'), {'pid': pid})
                    if blocked:
                        break
                    time.sleep(0.02)
            assert blocked, 'DELETE must wait for the concurrent UPDATE lock'
        finally:
            reactivating.commit()  # Release before joining even if assertion fails.
        assert future.result(timeout=5) == 409
    assert db.get(User, target_id).is_active


def test_repository_user_table_has_no_inbound_foreign_keys(users):
    _, db, _, _ = users
    assert not db.execute(text("""
        SELECT 1 FROM pg_constraint
        WHERE contype = 'f' AND confrelid = 'users'::regclass
    """)).all()
