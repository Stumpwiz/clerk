"""Generation route boundaries: synthetic authentication, stubbed I/O only."""
from types import SimpleNamespace

import pytest
from test_report_route_boundary import route_client, authenticate

REPORT_IDS = ['long-roster', 'short-roster', 'vacancies', 'expirations', 'terms-report',
              'rc-officers', 'rc-officers-and-chairs', 'committee-secretaries', 'hall-reps']
LIST_IDS = ['committee-chairs', 'committee-secretaries', 'hall-reps', 'rc-officers']
PATHS = ['/api/reports/' + name for name in REPORT_IDS] + ['/api/mailing-lists/' + name for name in LIST_IDS]
ORIGIN = 'https://clerk.mrrc.online'
PDF = b'%PDF-synthetic'


@pytest.fixture
def generation(route_client, monkeypatch, tmp_path):
    from app.routers import reports, mailing_lists
    from app.config import settings
    calls = []
    pdf = tmp_path / 'synthetic.pdf'
    pdf.write_bytes(PDF)
    text = tmp_path / 'synthetic.txt'
    text.write_text('synthetic@example.invalid')
    def render(**kwargs):
        calls.append('pdf')
        return pdf
    def write(*args):
        calls.append('text')
        return text
    def publish(**kwargs):
        calls.append('publish')
        return {'remote_path': '/synthetic.pdf'}
    monkeypatch.setattr(reports.pdf_generator, 'generate_pdf', render)
    monkeypatch.setattr(reports.pdf_generator, 'reports_dir', tmp_path)
    monkeypatch.setattr(mailing_lists.pdf_generator, 'reports_dir', tmp_path)
    monkeypatch.setattr(reports, 'write_email_list_file', write)
    monkeypatch.setattr(mailing_lists, 'write_email_list_file', write)
    monkeypatch.setattr(reports, 'upload_pdf_to_ionos', publish)
    monkeypatch.setattr(settings, 'enable_ionos_roster_publish', True)
    for entry in reports.REPORT_REGISTRY.values():
        monkeypatch.setattr(entry, 'builder_func', lambda db: {})
    for entry in mailing_lists.MAILING_LIST_REGISTRY.values():
        monkeypatch.setattr(entry, 'builder_func', lambda db: ['synthetic@example.invalid'])
    for name in ['get_rc_officers_emails', 'get_committee_chairs_emails', 'get_committee_secretaries_emails', 'get_hall_reps_emails']:
        monkeypatch.setattr(reports, name, lambda db: ['synthetic@example.invalid'])
    return route_client[0], calls


@pytest.mark.parametrize('path', PATHS)
@pytest.mark.parametrize('authenticated', [False, True])
def test_old_get_never_generates(generation, path, authenticated):
    client, calls = generation
    if authenticated:
        authenticate(client)
    assert client.get(path).status_code == 405
    assert calls == []


@pytest.mark.parametrize('path', PATHS)
def test_post_requires_authentication(generation, path):
    client, calls = generation
    assert client.post(path, headers={'Origin': ORIGIN}).status_code == 401
    assert calls == []


@pytest.mark.parametrize('headers', [[], [('Origin', 'null')], [('Origin', ORIGIN + '/')],
    [('Origin', 'https://evil.example')], [('Origin', ORIGIN), ('Origin', ORIGIN)]])
@pytest.mark.parametrize('path', PATHS)
def test_rejected_origin_never_generates_or_publishes(generation, path, headers):
    client, calls = generation
    authenticate(client)
    assert client.post(path, headers=headers).status_code == 403
    assert calls == []


@pytest.mark.parametrize('path', PATHS)
def test_trusted_post_preserves_response(generation, path):
    client, calls = generation
    authenticate(client)
    response = client.post(path, headers={'Origin': ORIGIN})
    assert response.status_code == 200
    is_pdf = path.rsplit('/', 1)[1] in REPORT_IDS[:5] and '/reports/' in path
    assert response.content == (PDF if is_pdf else b'synthetic@example.invalid')
    assert response.headers['content-type'].startswith('application/pdf' if is_pdf else 'text/plain')
    assert response.headers['content-disposition'].startswith('inline; filename=')
    assert calls == (['pdf', 'publish'] if path.endswith('/short-roster') else ['pdf'] if is_pdf else ['text'])


def test_publication_disabled(generation, monkeypatch):
    from app.config import settings
    client, calls = generation
    authenticate(client)
    monkeypatch.setattr(settings, 'enable_ionos_roster_publish', False)
    assert client.post('/api/reports/short-roster', headers={'Origin': ORIGIN}).status_code == 200
    assert calls == ['pdf']


def test_metadata_existing_downloads_and_letters(generation, monkeypatch):
    from app.routers import letters
    from app.database import get_db
    from app.models import User, GeneratedLetter, LetterTemplate
    client, calls = generation
    authenticate(client)
    for path in ['/api/reports', '/api/mailing-lists', '/api/reports/pdfs']:
        assert client.get(path).status_code == 200
    assert client.get('/api/reports/pdfs/synthetic.pdf').content == PDF
    class SyntheticDB:
        def get(self, model, identifier):
            if model is User:
                return User(id=42, is_active=True, session_version=0)
            assert model is GeneratedLetter
            return SimpleNamespace(pdf_bytes=PDF)
    monkeypatch.setitem(client.app.dependency_overrides, get_db, lambda: SyntheticDB())
    monkeypatch.setattr(LetterTemplate, 'get_singleton', lambda db: None)
    # Existing letter POST validation remains available, with no renderer needed.
    response = client.post('/api/letters/generate', headers={'Origin': ORIGIN}, json={
        'recipient': 'Synthetic User', 'salutation': 'Synthetic', 'apartment': '123', 'letter_date': '2026-01-01'})
    assert response.status_code == 200
    assert response.json()['success'] is False
    assert 'No template found' in response.json()['error']
    assert client.get('/api/letters/pdfs/synthetic.pdf').content == PDF
    assert calls == []


def test_letter_successful_generation_still_uses_post(generation, monkeypatch):
    from pathlib import Path
    from app.routers import letters
    from app.models import LetterTemplate
    from app.database import get_db
    client, calls = generation
    authenticate(client)
    saved = []
    old_dependency = client.app.dependency_overrides[get_db]
    def database():
        db = next(old_dependency())
        db.commit = lambda: saved.append('commit')
        db.rollback = lambda: pytest.fail('Unexpected letter rollback')
        yield db
    monkeypatch.setitem(client.app.dependency_overrides, get_db, database)
    monkeypatch.setattr(LetterTemplate, 'get_singleton', lambda db: SimpleNamespace(body='Welcome'))
    monkeypatch.setattr(letters, 'get_current_rc_president', lambda db: ('Synthetic President', '100'))
    monkeypatch.setattr(letters, 'build_latex_document', lambda **kwargs: 'synthetic latex')
    monkeypatch.setattr(letters.shutil, 'copyfile', lambda *args: None)
    def compile_stub(*args, **kwargs):
        (Path(kwargs['cwd']) / 'letter.pdf').write_bytes(b'%PDF-' + b'x' * 1200)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(letters.subprocess, 'run', compile_stub)
    monkeypatch.setattr(letters, 'save_generated_pdf', lambda db, filename, data: saved.append((filename, data)))
    response = client.post('/api/letters/generate', headers={'Origin': ORIGIN}, json={
        'recipient': 'Synthetic User', 'salutation': 'Synthetic', 'apartment': '123', 'letter_date': '2026-01-01'})
    assert response.status_code == 200
    assert response.json()['success'] is True
    assert saved[0][0] == response.json()['filename']
    assert saved[0][1].startswith(b'%PDF-')
    assert saved[1] == 'commit'
    assert calls == []
