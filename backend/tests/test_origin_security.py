"""Synthetic browser security checks; no production configuration or services."""
from http.cookies import SimpleCookie
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth.origin import configure_origin_protection
from app.auth.cookies import set_session_cookie, clear_session_cookie
from app.config import Settings, settings
from test_auth_local import _make_test_client

TRUSTED = 'https://frontend.example.com'


def production(**overrides):
    values = dict(CLERK_ENV='production', SESSION_COOKIE_SECURE=True,
                  AUTH_SECRET_KEY='synthetic-key-not-used-outside-tests', CORS_ORIGINS=[TRUSTED])
    values.update(overrides)
    with patch.dict('os.environ', {}, clear=True):
        return Settings(_env_file=None, **values)


@pytest.mark.parametrize('overrides', [
    {'SESSION_COOKIE_SECURE': False}, {'SESSION_COOKIE_SAMESITE': 'none'},
    {'SESSION_COOKIE_SAMESITE': 'strict'}, {'AUTH_SECRET_KEY': ''},
    {'AUTH_SECRET_KEY': '  '}, {'AUTH_SECRET_KEY': 'dev-auth-secret-change-me'},
    {'AUTH_SECRET_KEY': 'changeme'}, {'CORS_ORIGINS': []},
    {'CORS_ORIGINS': ['http://localhost:3000']}, {'CORS_ORIGINS': ['*']},
    {'CORS_ORIGINS': [TRUSTED + '/']}, {'CORS_ORIGINS': [TRUSTED + '?x']},
])
def test_production_rejects_unsafe_settings(overrides):
    with pytest.raises(ValidationError):
        production(**overrides)


@pytest.mark.parametrize('missing', ['AUTH_SECRET_KEY', 'CORS_ORIGINS'])
def test_production_requires_explicit_values(missing):
    values = dict(SESSION_COOKIE_SECURE=True, AUTH_SECRET_KEY='synthetic-key', CORS_ORIGINS=[TRUSTED])
    del values[missing]
    with patch.dict('os.environ', {}, clear=True), pytest.raises(ValidationError):
        Settings(_env_file=None, **values)  # Production is the safe default.


def test_valid_production_and_explicit_development():
    assert production().session_cookie_secure
    with patch.dict('os.environ', {}, clear=True):
        local = Settings(_env_file=None, CLERK_ENV='development')
        assert not local.session_cookie_secure
        assert 'http://localhost:3000' in local.cors_origins


@pytest.mark.parametrize('encoded', [TRUSTED, '["https://frontend.example.com"]'])
def test_allowlist_environment_parsing(encoded):
    with patch.dict('os.environ', {'CLERK_ENV': 'production', 'SESSION_COOKIE_SECURE': 'true',
                    'AUTH_SECRET_KEY': 'synthetic-key', 'CORS_ORIGINS': encoded}, clear=True):
        assert Settings(_env_file=None).cors_origins == [TRUSTED]


@pytest.fixture
def guarded():
    app = FastAPI()
    effects = []
    @app.api_route('/operation', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
    def operation():
        effects.append('called')
        return {'ok': True}
    configure_origin_protection(app, [TRUSTED])
    with TestClient(app) as client:
        yield client, effects


BAD_HEADERS = [[], [('Origin', 'null')], [('Origin', '')],
    [('Origin', 'http://frontend.example.com')], [('Origin', TRUSTED + ':444')],
    [('Origin', 'https://sub.frontend.example.com')], [('Origin', TRUSTED + '.evil.example')],
    [('Origin', TRUSTED + '/')], [('Origin', TRUSTED + '?x')],
    [('Origin', TRUSTED + '#x')], [('Origin', 'https://user@frontend.example.com')],
    [('Origin', TRUSTED + ', ' + TRUSTED)], [('Origin', TRUSTED + ' ' + TRUSTED)],
    [('Origin', TRUSTED), ('Origin', TRUSTED)], [('Origin', TRUSTED), ('Origin', 'null')],
    [('Origin', 'https://frontend.example.com:bad')], [('Origin', 'https://frontend.example.com:65536')]]


@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE'])
@pytest.mark.parametrize('headers', BAD_HEADERS)
def test_rejection_precedes_side_effects(guarded, method, headers):
    client, effects = guarded
    assert client.request(method, '/operation', headers=headers).status_code == 403
    assert effects == []


@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE'])
def test_trusted_origin_and_cors(guarded, method):
    client, effects = guarded
    response = client.request(method, '/operation', headers={'Origin': TRUSTED})
    assert response.status_code == 200
    assert effects == ['called']
    assert response.headers['access-control-allow-origin'] == TRUSTED
    assert response.headers['access-control-allow-credentials'] == 'true'


def test_preflight_and_read_only_get(guarded):
    client, effects = guarded
    response = client.options('/operation', headers={'Origin': TRUSTED, 'Access-Control-Request-Method': 'POST'})
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == TRUSTED
    assert effects == []
    response = client.options('/operation', headers={'Origin': 'https://evil.example', 'Access-Control-Request-Method': 'POST'})
    assert response.status_code == 400
    assert 'access-control-allow-origin' not in response.headers
    assert client.get('/operation').status_code == 200
    response = client.get('/operation', headers={'Origin': 'https://evil.example'})
    assert 'access-control-allow-origin' not in response.headers


def test_cookie_creation_deletion_match(monkeypatch):
    monkeypatch.setattr(settings, 'session_cookie_secure', True)
    monkeypatch.setattr(settings, 'session_cookie_samesite', 'lax')
    created, deleted = Response(), Response()
    set_session_cookie(created, 1, 0)
    clear_session_cookie(deleted)
    cookies = []
    for response in (created, deleted):
        cookie = SimpleCookie()
        cookie.load(response.headers['set-cookie'])
        cookies.append(cookie[settings.session_cookie_name])
    for attribute, expected in [('secure', True), ('httponly', True), ('samesite', 'lax'), ('path', '/'), ('domain', '')]:
        assert cookies[0][attribute] == cookies[1][attribute] == expected
    assert cookies[1]['max-age'] == '0'


def test_real_auth_routes_remain_authorized_and_guarded():
    client, engine = _make_test_client(is_admin=False)
    configure_origin_protection(client.app, [TRUSTED])
    try:
        assert client.post('/api/auth/login', json={'email': 'trusted@example.com', 'password': 'password123'}).status_code == 403
        client.headers['Origin'] = TRUSTED
        assert client.post('/api/auth/login', json={'email': 'trusted@example.com', 'password': 'password123'}).status_code == 200
        assert client.get('/api/auth/me').status_code == 200
        assert client.post('/api/users/2/reset-password', json={'new_password': 'replacement123'}).status_code == 403
        assert client.post('/api/auth/change-password', json={'current_password': 'password123', 'new_password': 'replacement123', 'confirm_password': 'replacement123'}).status_code == 200
        assert client.get('/api/auth/me').status_code == 401
        assert client.post('/api/auth/logout').status_code == 200
    finally:
        client.close()
        engine.dispose()


def test_admin_mutation_requires_origin_before_database_dependency():
    client, engine = _make_test_client()
    configure_origin_protection(client.app, [TRUSTED])
    try:
        from app.database import get_db
        original_dependency = client.app.dependency_overrides[get_db]
        def forbidden_database():
            raise AssertionError('Origin rejection must precede database dependencies')
        client.app.dependency_overrides[get_db] = forbidden_database
        for path in ['/api/auth/login', '/api/auth/logout', '/api/auth/change-password', '/api/users/2/reset-password']:
            assert client.post(path, json={}).status_code == 403
        client.app.dependency_overrides[get_db] = original_dependency
        client.headers['Origin'] = TRUSTED
        assert client.post('/api/users/2/reset-password', json={'new_password': 'replacement123'}).status_code == 401
        assert client.post('/api/auth/login', json={'email': 'trusted@example.com', 'password': 'password123'}).status_code == 200
        assert client.post('/api/users/2/reset-password', json={'new_password': 'replacement123'}).status_code == 200
    finally:
        client.close()
        engine.dispose()
