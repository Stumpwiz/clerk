"""
End-to-end PostgreSQL migration test suite.

Covers:
- Database connection (SQLite and PostgreSQL)
- Table creation via Alembic migrations
- Data migration from SQLite → PostgreSQL
- CRUD operations on PostgreSQL
- FK constraints enforcement
- Letter generation against PostgreSQL
- Report view reads on PostgreSQL

Run with:
  pytest -vv backend/tests/test_postgres_migration.py
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import IntegrityError


def test_can_connect_sqlite(sqlite_temp_db: str):
    eng = create_engine(sqlite_temp_db, connect_args={"check_same_thread": False})
    try:
        with eng.connect() as conn:
            assert conn.execute(text("select 1")).scalar() == 1
    finally:
        eng.dispose()


def test_can_connect_postgres(postgres_url: str):
    eng = create_engine(postgres_url, pool_pre_ping=True, future=True)
    try:
        with eng.connect() as conn:
            assert conn.execute(text("select 1")).scalar() == 1
    finally:
        eng.dispose()


def test_alembic_migration_creates_tables(migrated_postgres: str):
    eng = create_engine(migrated_postgres, pool_pre_ping=True, future=True)
    try:
        insp = inspect(eng)
        tables = set(insp.get_table_names(schema="public"))
        for t in ("body", "office", "person", "term", "letters"):
            assert t in tables, f"Missing table: {t}"
        # Check the view exists using inspector first, then fallback query
        try:
            view_names = set(insp.get_view_names(schema="public"))
            assert "report_record" in view_names, "report_record view missing"
        except Exception:
            # Fallback: attempt a zero-row select; if it errors, view is missing
            with eng.connect() as conn:
                conn.execute(text("SELECT 1 FROM report_record WHERE 1=0"))
    finally:
        eng.dispose()


def test_data_migration_from_sqlite(sqlite_temp_db: str, migrated_postgres: str):
    # Run the provided migration utility to copy data from sqlite_temp_db → migrated_postgres
    backend_dir = pathlib.Path(__file__).resolve().parents[1]
    script = backend_dir / "scripts" / "migrate_sqlite_to_postgres.py"
    env = os.environ.copy()
    env.update({
        "DATABASE_URL": sqlite_temp_db,
        "POSTGRES_URL": migrated_postgres,
    })
    subprocess.run(
        ["python", str(script), "--source", sqlite_temp_db, "--target", migrated_postgres, "--batch-size", "200"],
        cwd=str(backend_dir),
        check=True,
        env=env,
    )

    eng = create_engine(migrated_postgres, pool_pre_ping=True, future=True)
    try:
        with eng.connect() as conn:
            for t in ("body", "office", "person", "term", "letters"):
                cnt = conn.execute(text(f"select count(*) from {t}")).scalar()
                assert cnt and cnt > 0, f"Expected rows in {t} after migration"
    finally:
        eng.dispose()


def test_crud_and_relationships(pg_session):
    # Import models after DB is available
    from app.models import Body, Office, Person, Term, LetterTemplate

    # Create graph
    body = Body(name="Parks", mission="Keep green", body_precedence=1.0)
    pg_session.add(body)
    pg_session.flush()

    off = Office(title="Director", office_precedence=1.0, office_body_id=body.body_id)
    pg_session.add(off)
    pg_session.flush()

    ada = Person(first="Ada", last="Lovelace", email="ada@example.com", phone="555-0000", apt=None)
    pg_session.add(ada)
    pg_session.flush()

    term = Term(term_person_id=ada.person_id, term_office_id=off.office_id, ordinal="1st")
    pg_session.add(term)

    tmpl = LetterTemplate(header="Welcome", body="Hello world")
    pg_session.add(tmpl)
    pg_session.commit()

    # Read back
    got_off = pg_session.get(Office, off.office_id)
    assert got_off and got_off.body.body_id == body.body_id
    got_person = pg_session.get(Person, ada.person_id)
    assert got_person and got_person.terms[0].office.office_id == off.office_id

    # Update
    got_person.email = "ada.l@example.com"
    pg_session.commit()
    assert pg_session.get(Person, ada.person_id).email == "ada.l@example.com"

    # Delete dependency order
    pg_session.delete(term)
    pg_session.delete(got_person)
    pg_session.delete(got_off)
    pg_session.delete(pg_session.get(Body, body.body_id))
    pg_session.commit()


def test_fk_constraints_enforced(pg_session):
    # Import models after DB is available
    from app.models import Term

    # Invalid person and office ids should fail
    bad = Term(term_person_id=99999, term_office_id=88888, ordinal="X")
    pg_session.add(bad)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_letter_generation_helpers(pg_session):
    from app.models import LetterTemplate

    # Initially empty
    assert LetterTemplate.can_add_record(pg_session) is True
    assert LetterTemplate.get_singleton(pg_session) is None

    # Add one
    lt = LetterTemplate(header="H", body="B")
    pg_session.add(lt)
    pg_session.commit()

    assert LetterTemplate.can_add_record(pg_session) is False
    assert LetterTemplate.get_singleton(pg_session) is not None


def test_report_view_returns_rows(pg_session):
    from app.models import Body, Office, Person, Term, ReportRecord

    # Seed minimal graph
    b = Body(name="Housing Authority", mission="Serve", body_precedence=1.0)
    pg_session.add(b); pg_session.flush()
    o = Office(title="Chair", office_precedence=1.0, office_body_id=b.body_id)
    pg_session.add(o); pg_session.flush()
    p = Person(first="Ada", last="Lovelace")
    pg_session.add(p); pg_session.flush()
    t = Term(term_person_id=p.person_id, term_office_id=o.office_id, ordinal="1st")
    pg_session.add(t)
    pg_session.commit()

    # Query the view
    rec = pg_session.query(ReportRecord).first()
    assert rec is not None
    assert rec.first == "Ada" and rec.title == "Chair"
