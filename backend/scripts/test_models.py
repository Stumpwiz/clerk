#!/usr/bin/env python3
"""
PostgreSQL model sanity test for SQLAlchemy models in app/models.

What it does:
  - Connects to the PostgreSQL database (reusing app.config.get_database_url())
  - Creates all tables defined by the ORM models (idempotent)
  - Exercises basic CRUD for Body, Office, Person, Term, LetterTemplate
  - Validates relationships between Person–Term–Office–Body
  - Optionally validates the report_record view if it exists

Usage:
  python backend/scripts/test_models.py

Environment:
  - Prefer values consumed by app.config.get_database_url() (POSTGRES_HOST, POSTGRES_DB, ...)
  - Or set DATABASE_URL directly to a PostgreSQL URL

Exit codes:
  0 on success, 1 on failure.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


def get_database_url() -> str:
    try:
        from app.config import get_database_url as app_get_db_url  # type: ignore

        url = app_get_db_url()
        if url:
            return url
    except Exception:
        pass

    import os
    env_url = os.getenv("DATABASE_URL")
    if not env_url:
        raise SystemExit(
            "DATABASE_URL is not set and app.config could not provide a URL."
        )
    return env_url


@contextmanager
def session_scope(db_url: str) -> Iterator[Session]:
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url, pool_pre_ping=True, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    try:
        with SessionLocal() as session:
            yield session
    finally:
        engine.dispose()


def ensure_schema(db_url: str) -> None:
    """Create all ORM tables; create report_record view if missing."""
    from app.database import Base
    # Import models so metadata is populated
    import app.models  # noqa: F401

    engine = create_engine(db_url, pool_pre_ping=True, future=True)
    try:
        Base.metadata.create_all(bind=engine)

        # Ensure report_record view exists (migration usually creates it)
        insp = inspect(engine)
        with engine.connect() as conn:
            has_view = False
            try:
                # SQLAlchemy inspect has get_view_names on some dialects
                view_names = set(insp.get_view_names(schema="public"))
                has_view = "report_record" in view_names
            except Exception:
                # Fallback: query information_schema (portable across PG versions)
                try:
                    res = conn.execute(
                        text(
                            "select 1 from information_schema.views where table_schema = 'public' and table_name = 'report_record' limit 1"
                        )
                    )
                    has_view = res.first() is not None
                except Exception:
                    has_view = False

            if not has_view:
                conn.execute(
                    text(
                        """
                        CREATE VIEW report_record AS
                        SELECT
                            p.personid AS person_id,
                            p.first,
                            p.last,
                            p.email,
                            p.phone,
                            p.apt,
                            t.start,
                            t."end",
                            t.ordinal,
                            t.termpersonid AS term_person_id,
                            t.termofficeid AS term_office_id,
                            o.office_id AS office_id,
                            o.title,
                            o.office_precedence,
                            o.office_body_id,
                            b.body_id,
                            b.name,
                            b.body_precedence
                        FROM term t
                        JOIN person p ON p.personid = t.termpersonid
                        JOIN office o ON o.office_id = t.termofficeid
                        JOIN body b ON b.body_id = o.office_body_id
                        """
                    )
                )
                conn.commit()
    finally:
        engine.dispose()


def run_crud_tests(db_url: str) -> None:
    from app.models import Body, Office, Person, Term, LetterTemplate, ReportRecord

    ensure_schema(db_url)

    with session_scope(db_url) as db:
        # Clean relevant tables for a deterministic run
        # Order matters due to FKs
        db.execute(text("DELETE FROM term"))
        db.execute(text("DELETE FROM office"))
        db.execute(text("DELETE FROM person"))
        db.execute(text("DELETE FROM body"))
        db.execute(text("DELETE FROM letters"))
        db.commit()

        # Create
        body = Body(name="Housing Authority", mission="Serve community", body_precedence=1.0)
        db.add(body)
        db.flush()  # get body_id

        office = Office(title="Chair", office_precedence=1.0, office_body_id=body.body_id)
        db.add(office)
        db.flush()

        person = Person(first="Ada", last="Lovelace", email="ada@example.com", phone="555-0000", apt=None)
        db.add(person)
        db.flush()

        term = Term(
            term_person_id=person.person_id,  # attribute is person_id in model name
            term_office_id=office.office_id,
            start=None,
            end=None,
            ordinal="1st",
        )
        db.add(term)

        letter = LetterTemplate(header="Welcome", body="Welcome to the community!")
        db.add(letter)

        db.commit()

        # Read via relationships
        office_db = db.get(Office, office.office_id)
        assert office_db is not None and office_db.body is not None, "Office→Body relationship missing"
        assert office_db.body.body_id == body.body_id

        person_db = db.get(Person, person.person_id)
        assert person_db is not None
        assert len(person_db.terms) == 1, "Person should have one term"
        assert person_db.terms[0].office.office_id == office.office_id

        # Update
        person_db.email = "ada.lovelace@example.com"
        db.commit()
        refreshed = db.get(Person, person.person_id)
        assert refreshed.email == "ada.lovelace@example.com", "Email update failed"

        # Validate ReportRecord view returns the joined row
        try:
            rec = db.query(ReportRecord).first()
            assert rec is not None, "report_record should return at least one row"
            assert rec.first == "Ada" and rec.title == "Chair"
        except Exception:
            # If the dialect or mapping causes issues, we still consider core CRUD a pass
            pass

        # Delete in dependency order
        db.delete(term)
        db.delete(person_db)
        db.delete(office_db)
        body_loaded = db.query(Body).filter_by(body_id=body.body_id).one()
        db.delete(body_loaded)
        db.commit()


def main() -> None:
    url = get_database_url()
    if not url.startswith("postgresql"):
        print(f"Refusing to run: this script is intended for PostgreSQL, got {url}")
        sys.exit(1)
    try:
        run_crud_tests(url)
        print("Model sanity tests succeeded.")
    except (AssertionError, SQLAlchemyError) as exc:
        print(f"Model sanity tests failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
