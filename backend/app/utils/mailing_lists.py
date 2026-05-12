from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable, List

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Body, Office, Person, Term


def normalize_email(email: str | None) -> str | None:
    if email is None:
        return None
    cleaned = email.strip()
    if not cleaned:
        return None
    return cleaned


def dedupe_emails(emails: Iterable[str]) -> List[str]:
    seen = set()
    ordered = []
    for email in emails:
        key = email.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(email)
    return ordered


def format_email_lines(emails: List[str]) -> str:
    if not emails:
        return ""
    lines = []
    last_index = len(emails) - 1
    for index, email in enumerate(emails):
        suffix = "," if index < last_index else ""
        lines.append(f"{email}{suffix}")
    return "\n".join(lines)


def write_email_list_file(output_dir: Path, filename: str, emails: List[str]) -> Path:
    report_path = output_dir / filename
    content = format_email_lines(emails)
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(content)
    except (PermissionError, OSError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write mailing list file at {report_path}: {exc}",
        ) from exc
    return report_path


def query_term_emails(
    db: Session,
    *,
    body_name: str | None = None,
    office_title: str | None = None,
    exclude_body_name: str | None = None,
    current_only: bool = False,
) -> List[str]:
    query = (
        db.query(Person.email)
        .select_from(Term)
        .join(Person, Person.person_id == Term.term_person_id)
        .join(Office, Office.office_id == Term.term_office_id)
        .join(Body, Body.body_id == Office.office_body_id)
    )

    if body_name is not None:
        query = query.filter(Body.name == body_name)
    if exclude_body_name is not None:
        query = query.filter(Body.name != exclude_body_name)
    if office_title is not None:
        query = query.filter(Office.title == office_title)
    if current_only:
        today = date.today()
        query = query.filter(
            Term.start <= today,
            (Term.end.is_(None)) | (Term.end >= today),
        )

    query = query.order_by(
        Body.body_precedence.asc(),
        Office.office_precedence.asc(),
        Person.last.asc(),
        Person.first.asc(),
    )

    raw_emails = []
    for (email,) in query.all():
        cleaned = normalize_email(email)
        if cleaned is None:
            continue
        raw_emails.append(cleaned)

    return dedupe_emails(raw_emails)


def get_rc_officers_emails(db: Session) -> List[str]:
    return query_term_emails(db, body_name="Residents Council")


def get_committee_chairs_emails(db: Session) -> List[str]:
    return query_term_emails(
        db,
        office_title="Chair",
        current_only=True,
    )


def get_committee_secretaries_emails(db: Session) -> List[str]:
    return query_term_emails(
        db,
        office_title="Secretary",
        current_only=True,
    )


def get_hall_reps_emails(db: Session) -> List[str]:
    normalized_body_name = func.lower(Body.name)
    query = (
        db.query(Person.email)
        .select_from(Term)
        .join(Person, Person.person_id == Term.term_person_id)
        .join(Office, Office.office_id == Term.term_office_id)
        .join(Body, Body.body_id == Office.office_body_id)
        .filter(
            normalized_body_name.like("% hall rep%"),
            Term.start <= date.today(),
            (Term.end.is_(None)) | (Term.end >= date.today()),
        )
        .order_by(
            Body.body_precedence.asc(),
            Office.office_precedence.asc(),
            Person.last.asc(),
            Person.first.asc(),
        )
    )

    raw_emails = []
    for (email,) in query.all():
        cleaned = normalize_email(email)
        if cleaned is None:
            continue
        raw_emails.append(cleaned)

    return dedupe_emails(raw_emails)
