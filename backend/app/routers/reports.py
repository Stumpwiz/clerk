# app/routers/reports.py - API endpoints for roster and report generation

import logging
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import List, Iterable

from app.database import get_db
from app.models import ReportRecord, Term, Person, Office, Body
from app.utils.pdf_generator import PDFGenerator
from app.utils.ionos_publisher import IONOSPublisherError, upload_pdf_to_ionos
from app.config import settings

router = APIRouter(prefix="/api/reports", tags=["reports"])
logger = logging.getLogger(__name__)

# Initialize PDF generator
pdf_generator = PDFGenerator(settings.roster_reports_dir)


ALLOWED_REPORT_SUFFIXES = {".pdf", ".txt"}


def _normalize_email(email: str | None) -> str | None:
    if email is None:
        return None
    cleaned = email.strip()
    if not cleaned:
        return None
    return cleaned


def _dedupe_emails(emails: Iterable[str]) -> List[str]:
    seen = set()
    ordered = []
    for email in emails:
        key = email.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(email)
    return ordered


def _format_email_lines(emails: List[str]) -> str:
    if not emails:
        return ""
    lines = []
    last_index = len(emails) - 1
    for index, email in enumerate(emails):
        suffix = "," if index < last_index else ""
        lines.append(f"{email}{suffix}")
    return "\n".join(lines)


def _write_text_report(filename: str, emails: List[str]) -> Path:
    report_path = pdf_generator.reports_dir / filename
    content = _format_email_lines(emails)
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(content)
    except (PermissionError, OSError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write report file at {report_path}: {exc}"
        ) from exc
    return report_path


def _query_emails(
    db: Session,
    *,
    body_name: str | None = None,
    office_title: str | None = None,
    exclude_body_name: str | None = None,
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

    query = query.order_by(Body.body_precedence.asc(), Office.office_precedence.asc())

    raw_emails = []
    for (email,) in query.all():
        cleaned = _normalize_email(email)
        if cleaned is None:
            continue
        raw_emails.append(cleaned)

    return _dedupe_emails(raw_emails)


def _build_vacancies_dataset(db: Session) -> tuple[List[ReportRecord], dict[str, List[ReportRecord]]]:
    # Query records where first name starts with "(Vacan"
    records = db.query(ReportRecord).filter(
        ReportRecord.first.like('(Vacan%')
    ).order_by(
        ReportRecord.body_precedence,
        ReportRecord.office_precedence,
        ReportRecord.first,
        ReportRecord.last
    ).all()

    # Group by body and prepare display data
    grouped = defaultdict(list)
    processed = []
    for record in records:
        # Check if truly vacant
        is_vacant = (
                record.first and
                record.first.startswith("(Vacan") and
                record.last == " "
        )

        # Create display name
        if is_vacant:
            full_name = record.first
        else:
            full_name = f"{record.first or ''} {record.last or ''}".strip()

        # Add custom attributes for template
        record.is_vacant = is_vacant
        record.incumbent_display = full_name
        grouped[record.name].append(record)
        processed.append(record)

    return processed, dict(grouped)


def _format_terms_office(record: ReportRecord) -> str:
    base = " ".join(part for part in [record.name, record.title] if part)
    ordinal = (record.ordinal or "").strip()
    if ordinal:
        return f"{base}, {ordinal}"
    return base


@router.get("/pdfs", response_model=List[dict])
async def list_report_pdfs():
    """List all available report files"""
    try:
        report_files = []
        reports_dir = pdf_generator.reports_dir

        if reports_dir.exists():
            for report_file in reports_dir.iterdir():
                if not report_file.is_file():
                    continue
                if report_file.suffix not in ALLOWED_REPORT_SUFFIXES:
                    continue
                report_files.append({
                    "filename": report_file.name,
                    "size": report_file.stat().st_size,
                    "modified": report_file.stat().st_mtime
                })

        # Sort by filename
        report_files.sort(key=lambda x: x["filename"])
        return report_files

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdfs/{filename}")
async def serve_report_file(filename: str):
    """Serve a specific report file"""
    try:
        # Security: Only allow known report types and prevent path traversal
        if "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        report_path = pdf_generator.reports_dir / filename
        if report_path.suffix not in ALLOWED_REPORT_SUFFIXES:
            raise HTTPException(status_code=400, detail="Invalid filename")

        if not report_path.exists():
            raise HTTPException(status_code=404, detail="Report not found")

        media_type = "application/pdf"
        if report_path.suffix == ".txt":
            media_type = "text/plain; charset=utf-8"

        return FileResponse(
            path=str(report_path),
            media_type=media_type,
            filename=filename,
            headers={"Content-Disposition": f"inline; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/long-roster")
async def generate_long_roster(db: Session = Depends(get_db)):
    """Generate long form roster with full details"""
    try:
        # Query all records, sorted by body and office precedence
        records = db.query(ReportRecord).order_by(
            ReportRecord.body_precedence,
            ReportRecord.office_precedence,
            ReportRecord.first,
            ReportRecord.last
        ).all()

        # Group by body name
        grouped = defaultdict(list)
        for record in records:
            grouped[record.name].append(record)

        # Generate PDF
        context = {
            "generated": pdf_generator.get_generation_timestamp(),
            "title": "Long Form Roster",
            "grouped": dict(grouped)
        }

        pdf_path = pdf_generator.generate_pdf(
            template_name="lfr_template.tex",
            output_name="long_form_roster",
            context=context
        )

        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename="long_form_roster.pdf",
            headers={"Content-Disposition": "inline; filename=long_form_roster.pdf"}
        )

    except Exception as e:
        logger.exception("Long roster generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/short-roster")
async def generate_short_roster(db: Session = Depends(get_db)):
    """Generate short form roster (names and offices only)"""
    try:
        # Query all records, sorted by body and office precedence
        records = db.query(ReportRecord).order_by(
            ReportRecord.body_precedence,
            ReportRecord.office_precedence,
            ReportRecord.first,
            ReportRecord.last
        ).all()

        # Group by body name
        grouped = defaultdict(list)
        for record in records:
            grouped[record.name].append(record)

        # Generate PDF
        context = {
            "generated": pdf_generator.get_generation_timestamp(),
            "title": "Short Form Roster",
            "grouped": dict(grouped)
        }

        pdf_path = pdf_generator.generate_pdf(
            template_name="sfr_template.tex",
            output_name="short_form_roster",
            context=context
        )

        raw_publish_flag = os.getenv("ENABLE_IONOS_ROSTER_PUBLISH", "")
        publish_enabled = raw_publish_flag.strip().lower() == "true"
        remote_path = "/mrra/documents/roster.pdf"

        if publish_enabled:
            try:
                publish_result = upload_pdf_to_ionos(
                    local_pdf_path=pdf_path,
                    secret_name=settings.ionos_sftp_secret_name,
                    aws_region=settings.aws_region,
                    remote_path=remote_path,
                )
                logger.info(
                    "Short roster published to IONOS: %s",
                    publish_result["remote_path"],
                )
            except IONOSPublisherError as exc:
                # Keep existing FileResponse API contract for this route;
                # publish status can be surfaced in JSON in a future route revision.
                logger.exception("IONOS short roster publish failed: %s", exc)
            except Exception as exc:
                logger.exception(
                    "IONOS short roster publish failed: unexpected_error=%s",
                    exc.__class__.__name__,
                )

        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename="short_form_roster.pdf",
            headers={"Content-Disposition": "inline; filename=short_form_roster.pdf"}
        )

    except Exception as e:
        logger.exception("Short roster generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vacancies")
async def generate_vacancies_report(db: Session = Depends(get_db)):
    """Generate report of vacant positions"""
    try:
        _, grouped = _build_vacancies_dataset(db)

        # Generate PDF
        context = {
            "generated": pdf_generator.get_generation_timestamp(),
            "title": "Vacancies",
            "grouped": grouped
        }

        pdf_path = pdf_generator.generate_pdf(
            template_name="vacancies_template.tex",
            output_name="vacancies_report",
            context=context
        )

        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename="vacancies_report.pdf",
            headers={"Content-Disposition": "inline; filename=vacancies_report.pdf"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vacancies/data", response_model=List[dict])
async def get_vacancies_data(db: Session = Depends(get_db)):
    """Return vacancies dataset used for the vacancies report"""
    try:
        records, _ = _build_vacancies_dataset(db)
        data = []
        for record in records:
            person_name = None
            if not record.is_vacant:
                person_name = record.incumbent_display or None
            data.append({
                "body_name": record.name,
                "office_title": record.title,
                "is_vacant": record.is_vacant,
                "person_name": person_name,
                "term_start": record.start.isoformat() if record.start else None,
                "term_end": record.end.isoformat() if record.end else None,
            })

        data.sort(key=lambda item: (item["body_name"] or "", item["office_title"] or ""))
        return data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expirations")
async def generate_expirations_report(db: Session = Depends(get_db)):
    """Generate report of terms expiring this year"""
    try:
        # Get current year
        current_year = datetime.now().year

        # Query records with terms ending this year
        records = db.query(ReportRecord).filter(
            ReportRecord.end.between(
                f"{current_year}-01-01",
                f"{current_year}-12-31"
            )
        ).order_by(
            ReportRecord.body_precedence,
            ReportRecord.office_precedence,
            ReportRecord.first,
            ReportRecord.last
        ).all()

        # Group by body and format dates
        grouped = defaultdict(list)
        for record in records:
            # Format end date for display
            record.formatted_end = (
                record.end.strftime("%Y-%m-%d") if record.end else ""
            )
            grouped[record.name].append(record)

        # Generate PDF
        context = {
            "generated": pdf_generator.get_generation_timestamp(),
            "title": f"Expirations — {current_year}",
            "grouped": dict(grouped)
        }

        pdf_path = pdf_generator.generate_pdf(
            template_name="expirations_template.tex",
            output_name="expirations_report",
            context=context
        )

        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename="expirations_report.pdf",
            headers={"Content-Disposition": "inline; filename=expirations_report.pdf"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/terms-report")
async def generate_terms_report(db: Session = Depends(get_db)):
    """Generate report of all terms with actual expiration dates"""
    try:
        records = db.query(ReportRecord).filter(
            ReportRecord.end < date(9999, 12, 31),
            ReportRecord.title != "Liaison",
            ReportRecord.title != "Staff",
        ).order_by(
            ReportRecord.body_precedence,
            ReportRecord.office_precedence,
            ReportRecord.first,
            ReportRecord.last
        ).all()

        rows = []
        for record in records:
            rows.append({
                "name": f"{record.first or ''} {record.last or ''}".strip(),
                "office": _format_terms_office(record),
                "start": record.start.strftime("%Y-%m-%d") if record.start else "",
                "end": record.end.strftime("%Y-%m-%d") if record.end else "",
            })

        context = {
            "generated": pdf_generator.get_generation_timestamp(),
            "title": "Terms with Expiration Dates",
            "rows": rows
        }

        pdf_path = pdf_generator.generate_pdf(
            template_name="terms_template.tex",
            output_name="terms_report",
            context=context
        )

        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename="terms_report.pdf",
            headers={"Content-Disposition": "inline; filename=terms_report.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rc-officers")
async def generate_rc_officers_email_list(db: Session = Depends(get_db)):
    """Generate Residents Council officers email list"""
    try:
        emails = _query_emails(db, body_name="Residents Council")
        report_path = _write_text_report("rc_officers.txt", emails)
        return FileResponse(
            path=str(report_path),
            media_type="text/plain; charset=utf-8",
            filename="rc_officers.txt",
            headers={"Content-Disposition": "inline; filename=rc_officers.txt"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rc-officers-and-chairs")
async def generate_rc_officers_and_chairs_email_list(db: Session = Depends(get_db)):
    """Generate combined RC officers + committee chairs email list"""
    try:
        officers = _query_emails(db, body_name="Residents Council")
        chairs = _query_emails(
            db,
            office_title="Chair",
            exclude_body_name="Residents Council"
        )
        combined = _dedupe_emails(officers + chairs)
        report_path = _write_text_report("rc_officers_and_chairs.txt", combined)
        return FileResponse(
            path=str(report_path),
            media_type="text/plain; charset=utf-8",
            filename="rc_officers_and_chairs.txt",
            headers={"Content-Disposition": "inline; filename=rc_officers_and_chairs.txt"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _get_committee_secretaries_emails(db: Session) -> List[str]:
    """Helper to query committee secretaries emails"""
    return _query_emails(
        db,
        office_title="Secretary",
        exclude_body_name="Residents Council"
    )


@router.get("/committee-secretaries")
async def generate_committee_secretaries_email_list(db: Session = Depends(get_db)):
    """Generate committee secretaries email list"""
    try:
        emails = _get_committee_secretaries_emails(db)
        report_path = _write_text_report("committee_secretaries.txt", emails)
        return FileResponse(
            path=str(report_path),
            media_type="text/plain; charset=utf-8",
            filename="committee_secretaries.txt",
            headers={"Content-Disposition": "inline; filename=committee_secretaries.txt"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
