import os
import pytest
from datetime import date, timedelta

from app.models.person import Person
from app.models.body import Body
from app.models.office import Office
from app.models.term import Term

# Adjust if needed to the real location:
from app.routers.reports import _get_committee_secretaries_emails, _get_hall_reps_emails


@pytest.fixture(scope="session", autouse=True)
def _use_docker_postgres_for_tests(postgres_test_db):
    """
    Ensure DATABASE_URL is set so the postgres_url fixture does not skip.
    Uses the Docker-provisioned postgres_test_db from conftest.py.
    """
    os.environ["DATABASE_URL"] = postgres_test_db
    yield


def test_committee_secretaries_excludes_residents_council_secretary(pg_session):
    # Use "unlikely" IDs to avoid collisions
    rc_body = Body(body_id=9001, name="Residents Council", body_precedence=1.0)
    committee_body = Body(body_id=9002, name="Landscape Committee", body_precedence=2.0)
    pg_session.add_all([rc_body, committee_body])
    pg_session.flush()

    rc_secretary_office = Office(
        title="Secretary",
        office_precedence=1.0,
        office_body_id=rc_body.body_id,
    )
    committee_secretary_office = Office(
        title="Secretary",
        office_precedence=1.0,
        office_body_id=committee_body.body_id,
    )
    pg_session.add_all([rc_secretary_office, committee_secretary_office])
    pg_session.flush()

    rc_secretary = Person(first="RC", last="Secretary", email="rc.secretary@example.org")
    committee_secretary = Person(first="Committee", last="Secretary", email="committee.secretary@example.org")
    pg_session.add_all([rc_secretary, committee_secretary])
    pg_session.flush()

    pg_session.add_all([
        Term(term_person_id=rc_secretary.person_id, term_office_id=rc_secretary_office.office_id),
        Term(term_person_id=committee_secretary.person_id, term_office_id=committee_secretary_office.office_id),
    ])
    pg_session.commit()

    emails = _get_committee_secretaries_emails(pg_session)

    assert "committee.secretary@example.org" in emails
    assert "rc.secretary@example.org" not in emails


def test_hall_reps_includes_only_active_with_email_and_dedupes(pg_session):
    hall_body = Body(body_id=9101, name="North Hall", body_precedence=3.0)
    pg_session.add(hall_body)
    pg_session.flush()

    hall_rep_office = Office(
        title="Hall Representative",
        office_precedence=1.0,
        office_body_id=hall_body.body_id,
    )
    hall_rep_alt_office = Office(
        title="Hall-Rep East",
        office_precedence=2.0,
        office_body_id=hall_body.body_id,
    )
    non_hall_office = Office(
        title="Secretary",
        office_precedence=3.0,
        office_body_id=hall_body.body_id,
    )
    pg_session.add_all([hall_rep_office, hall_rep_alt_office, non_hall_office])
    pg_session.flush()

    active = Person(first="Active", last="Rep", email="active.rep@example.org")
    expired = Person(first="Expired", last="Rep", email="expired.rep@example.org")
    future = Person(first="Future", last="Rep", email="future.rep@example.org")
    missing_email = Person(first="No", last="Email", email="   ")
    duplicate = Person(first="Dupe", last="Rep", email="dupe.rep@example.org")
    not_hall_rep = Person(first="Not", last="Hall", email="not.hall@example.org")
    pg_session.add_all([active, expired, future, missing_email, duplicate, not_hall_rep])
    pg_session.flush()

    today = date.today()
    pg_session.add_all([
        # Included: active term with email
        Term(
            term_person_id=active.person_id,
            term_office_id=hall_rep_office.office_id,
            start=today - timedelta(days=30),
            end=today + timedelta(days=30),
        ),
        # Excluded: expired term
        Term(
            term_person_id=expired.person_id,
            term_office_id=hall_rep_office.office_id,
            start=today - timedelta(days=120),
            end=today - timedelta(days=1),
        ),
        # Excluded: future term
        Term(
            term_person_id=future.person_id,
            term_office_id=hall_rep_office.office_id,
            start=today + timedelta(days=1),
            end=today + timedelta(days=120),
        ),
        # Excluded: blank email
        Term(
            term_person_id=missing_email.person_id,
            term_office_id=hall_rep_office.office_id,
            start=today - timedelta(days=10),
            end=today + timedelta(days=10),
        ),
        # Included once: same person has two active hall-rep terms
        Term(
            term_person_id=duplicate.person_id,
            term_office_id=hall_rep_office.office_id,
            start=today - timedelta(days=30),
            end=today + timedelta(days=30),
        ),
        Term(
            term_person_id=duplicate.person_id,
            term_office_id=hall_rep_alt_office.office_id,
            start=today - timedelta(days=30),
            end=today + timedelta(days=30),
        ),
        # Excluded: not a hall-rep office title
        Term(
            term_person_id=not_hall_rep.person_id,
            term_office_id=non_hall_office.office_id,
            start=today - timedelta(days=10),
            end=today + timedelta(days=10),
        ),
    ])
    pg_session.commit()

    emails = _get_hall_reps_emails(pg_session)

    assert "active.rep@example.org" in emails
    assert emails.count("dupe.rep@example.org") == 1
    assert "expired.rep@example.org" not in emails
    assert "future.rep@example.org" not in emails
    assert "not.hall@example.org" not in emails
