"""PDF lifecycle tests against an explicitly selected disposable PostgreSQL DB."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, inspect
from sqlalchemy.orm import Session

from app.auth.cookies import create_session_cookie_value
from app.database import get_db
from app.letter_storage import import_manifest
from app.models import GeneratedLetter, LetterTemplate, User
from app.routers import letters

PDF = b'%PDF-1.4\n' + b'x' * 1200
PAYLOAD = dict(recipient='Jane Smith', salutation='Jane', apartment='123', letter_date='2026-09-03')


def make_client(db):
    app = FastAPI()
    app.include_router(letters.router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def context(pg_session, monkeypatch, tmp_path):
    user = User(email='letters@example.com', display_name='Letters', password_hash='unused', is_active=True)
    pg_session.add_all([user, LetterTemplate(header='', body='Welcome to our community.')])
    pg_session.commit()
    client = make_client(pg_session)
    client.cookies.set('clerk_session', create_session_cookie_value(user.id))
    monkeypatch.setattr(letters, 'get_current_rc_president', lambda db: ('Test President', '100'))
    workspaces = []

    def compile_pdf(*args, **kwargs):
        work = Path(kwargs['cwd'])
        workspaces.append(work)
        assert (work / 'residentCouncilLogoSmall.jpg').exists()
        (work / 'letter.pdf').write_bytes(PDF)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(letters.subprocess, 'run', compile_pdf)
    return client, pg_session, workspaces, user.id


def test_generate_list_retrieve_delete_and_duplicate(context):
    client, db, workspaces, _ = context
    for _ in range(2):
        response = client.post('/api/letters/generate', json=PAYLOAD)
        assert response.json() == {'success': True, 'filename': '2026-09-03_Smith.pdf', 'error': None}
    assert len(set(workspaces)) == 2
    assert all(not path.exists() for path in workspaces)
    assert client.get('/api/letters/pdfs').json() == [dict(filename='2026-09-03_Smith.pdf', date_prefix='2026-09-03')]
    response = client.get('/api/letters/pdfs/2026-09-03_Smith.pdf')
    assert response.content == PDF
    assert response.headers['content-type'] == 'application/pdf'
    assert response.headers['content-disposition'].startswith('inline;')
    assert db.scalar(select(GeneratedLetter)).created_at is not None
    assert client.delete('/api/letters/pdfs/2026-09-03_Smith.pdf').status_code == 204
    assert client.get('/api/letters/pdfs').json() == []
    assert client.get('/api/letters/pdfs/2026-09-03_Smith.pdf').status_code == 404
    assert client.delete('/api/letters/pdfs/2026-09-03_Smith.pdf').status_code == 404


def test_duplicate_replaces_bytes_preserves_creation(context, monkeypatch):
    client, db, _, _ = context
    client.post('/api/letters/generate', json=PAYLOAD)
    original_time = db.get(GeneratedLetter, '2026-09-03_Smith.pdf').created_at
    def compile_pdf(*args, **kwargs):
        (Path(kwargs['cwd']) / 'letter.pdf').write_bytes(PDF + b'new')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(letters.subprocess, 'run', compile_pdf)
    assert client.post('/api/letters/generate', json=PAYLOAD).json()['success']
    assert client.get('/api/letters/pdfs/2026-09-03_Smith.pdf').content == PDF + b'new'
    assert db.get(GeneratedLetter, '2026-09-03_Smith.pdf').created_at == original_time


@pytest.mark.parametrize('mode', ['exit', 'missing', 'invalid', 'timeout', 'commit'])
def test_failures_do_not_replace_existing_pdf(context, monkeypatch, mode):
    client, db, _, _ = context
    assert client.post('/api/letters/generate', json=PAYLOAD).json()['success']
    paths = []
    def fail(*args, **kwargs):
        path = Path(kwargs['cwd']); paths.append(path)
        if mode == 'timeout':
            raise subprocess.TimeoutExpired('xelatex', 30)
        if mode == 'invalid':
            (path / 'letter.pdf').write_bytes(b'bad')
        if mode == 'commit':
            (path / 'letter.pdf').write_bytes(PDF + b'changed')
        return SimpleNamespace(returncode=1 if mode == 'exit' else 0)
    monkeypatch.setattr(letters.subprocess, 'run', fail)
    if mode == 'commit':
        monkeypatch.setattr(db, 'commit', lambda: (_ for _ in ()).throw(RuntimeError('private SQL parameters')))
    result = client.post('/api/letters/generate', json=PAYLOAD).json()
    assert result['success'] is False
    assert 'private SQL' not in result['error']
    assert all(not path.exists() for path in paths)
    assert client.get('/api/letters/pdfs/2026-09-03_Smith.pdf').content == PDF


def test_authentication(context):
    client, db, _, user_id = context
    for inactive in (False, True):
        if inactive:
            client.cookies.set('clerk_session', create_session_cookie_value(user_id))
            db.get(User, user_id).is_active = False
            db.commit()
        else:
            client.cookies.clear()
        assert client.get('/api/letters/pdfs').status_code == 401
        assert client.get('/api/letters/pdfs/test.pdf').status_code == 401
        assert client.delete('/api/letters/pdfs/test.pdf').status_code == 401
        assert client.post('/api/letters/generate', json=PAYLOAD).status_code == 401


def test_ordering_and_empty_filesystem_after_app_replacement(context, tmp_path, monkeypatch):
    client, db, _, user_id = context
    names = ['z.pdf', '2026-09-03_B.pdf', '2026-01-01_A.pdf', '2026-99-99_bad.pdf', 'a.pdf']
    db.add_all([GeneratedLetter(filename=name, pdf_bytes=PDF) for name in names]); db.commit()
    monkeypatch.chdir(tmp_path)
    assert list(tmp_path.iterdir()) == []
    # New app and DB session with no local PDFs or previous ORM state.
    with Session(db.bind) as replacement_db:
        replacement = make_client(replacement_db)
        replacement.cookies.set('clerk_session', create_session_cookie_value(user_id))
        result = replacement.get('/api/letters/pdfs').json()
        assert [x['filename'] for x in result] == ['2026-01-01_A.pdf', '2026-09-03_B.pdf', '2026-99-99_bad.pdf', 'a.pdf', 'z.pdf']
        assert result[2]['date_prefix'] is None
        for name in names:
            assert replacement.get('/api/letters/pdfs/' + name).content == PDF
    assert list(tmp_path.iterdir()) == []


def manifest(tmp_path, entries):
    records = []
    for name, data in entries:
        (tmp_path / name).write_bytes(data)
        records.append(dict(filename=name, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps({'files': records}))
    return path


def test_import_integrity_idempotence_and_conflict(pg_session, tmp_path):
    path = manifest(tmp_path, [('a.pdf', PDF), ('b.pdf', PDF + b'b')])
    assert import_manifest(pg_session, path, dry_run=True) == {'would_insert': 2, 'identical': 0}
    assert pg_session.scalar(select(GeneratedLetter)) is None
    assert import_manifest(pg_session, path) == {'inserted': 2, 'identical': 0}
    assert import_manifest(pg_session, path) == {'inserted': 0, 'identical': 2}
    path = manifest(tmp_path, [('new.pdf', PDF), ('a.pdf', PDF + b'conflict')])
    with pytest.raises(ValueError, match='Filename conflict'):
        import_manifest(pg_session, path)
    assert pg_session.get(GeneratedLetter, 'new.pdf') is None
    assert pg_session.get(GeneratedLetter, 'a.pdf').pdf_bytes == PDF


@pytest.mark.parametrize('damage', ['bytes', 'size', 'checksum', 'duplicate', 'path'])
def test_import_rejects_bad_manifest_without_partial_rows(pg_session, tmp_path, damage):
    path = manifest(tmp_path, [('good.pdf', PDF), ('bad.pdf', PDF)])
    data = json.loads(path.read_text())
    if damage == 'bytes': (tmp_path / 'bad.pdf').write_bytes(b'broken')
    if damage == 'size': data['files'][1]['size_bytes'] += 1
    if damage == 'checksum': data['files'][1]['sha256'] = '0' * 64
    if damage == 'duplicate': data['files'][1] = data['files'][0]
    if damage == 'path': data['files'][1]['filename'] = '../bad.pdf'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError): import_manifest(pg_session, path)
    assert pg_session.scalar(select(GeneratedLetter)) is None


def test_generated_letter_schema(pg_session):
    inspector = inspect(pg_session.bind)
    columns = {c['name']: c for c in inspector.get_columns('generated_letters')}
    assert set(columns) == {'filename', 'pdf_bytes', 'created_at'}
    assert all(not c['nullable'] for c in columns.values())
    assert inspector.get_pk_constraint('generated_letters')['constrained_columns'] == ['filename']


def test_import_commit_failure_rolls_back_all_rows(pg_session, tmp_path, monkeypatch):
    path = manifest(tmp_path, [('first.pdf', PDF), ('second.pdf', PDF)])
    def fail_commit():
        raise RuntimeError('commit failed')
    monkeypatch.setattr(pg_session, 'commit', fail_commit)
    with pytest.raises(RuntimeError):
        import_manifest(pg_session, path)
    assert pg_session.scalar(select(GeneratedLetter)) is None


def test_import_cli_dry_run_apply_repeat_and_conflict(pg_session, tmp_path):
    path = manifest(tmp_path, [('cli.pdf', PDF)])
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'import_generated_letters.py'
    env = dict(os.environ, DATABASE_URL=pg_session.bind.url.render_as_string(hide_password=False))
    def run(*options):
        return REAL_RUN([sys.executable, str(script), str(path), *options],
                        env=env, capture_output=True, text=True, timeout=20)
    result = run()
    assert result.returncode == 0 and "'would_insert': 1" in result.stdout
    assert pg_session.get(GeneratedLetter, 'cli.pdf') is None
    result = run('--apply')
    assert result.returncode == 0 and "'inserted': 1" in result.stdout
    result = run('--apply')
    assert result.returncode == 0 and "'identical': 1" in result.stdout
    manifest(tmp_path, [('cli.pdf', PDF + b'changed')])
    result = run('--apply')
    assert result.returncode == 1 and 'Filename conflict' in result.stderr
    assert pg_session.get(GeneratedLetter, 'cli.pdf').pdf_bytes == PDF


def test_real_latex_generation(context, monkeypatch):
    if not shutil.which('xelatex'):
        pytest.skip('XeLaTeX is not installed')
    client, _, _, _ = context
    # Undo the fixture's subprocess stub only, retaining the test president.
    monkeypatch.setattr(letters.subprocess, 'run', REAL_RUN)
    response = client.post('/api/letters/generate', json=PAYLOAD)
    assert response.json()['success'], response.json()
    assert client.get('/api/letters/pdfs/2026-09-03_Smith.pdf').content.startswith(b'%PDF-')


REAL_RUN = subprocess.run
