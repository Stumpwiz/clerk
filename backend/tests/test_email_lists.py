import os
import pytest

from app.models.person import Person
from app.models.body import Body
from app.models.office import Office
from app.models.term import Term

# Adjust if needed to the real location:
from app.routers.reports import _get_committee_secretaries_emails


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