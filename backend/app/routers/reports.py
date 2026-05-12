# app/routers/reports.py - API endpoints for roster and report generation

import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass

from app.database import get_db
from app.models import ReportRecord
from app.utils.pdf_generator import PDFGenerator
from app.utils.ionos_publisher import IONOSPublisherError, upload_pdf_to_ionos
from app.utils.mailing_lists import (
    get_committee_chairs_emails,
    get_committee_secretaries_emails,
    get_hall_reps_emails,
    get_rc_officers_emails,
    write_email_list_file,
)
from app.config import settings

router = APIRouter(prefix="/api/reports", tags=["reports"])
logger = logging.getLogger(__name__)

# Initialize PDF generator
pdf_generator = PDFGenerator(settings.roster_reports_dir)


ALLOWED_REPORT_SUFFIXES = {".pdf"}


@dataclass
class ReportRegistryEntry:
    id: str
    label: str
    description: str
    filename: str
    renderer_type: str  # "latex_pdf" or "plain_text_file"
    template: Optional[str] = None
    builder_func: Optional[Callable[[Session], Any]] = None


class ReportMetadata(BaseModel):
    id: str
    label: str
    description: str
    filename: str
    renderer_type: str


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


# --- Data Builder Functions ---

def _build_long_roster_data(db: Session) -> Dict[str, Any]:
    records = db.query(ReportRecord).order_by(
        ReportRecord.body_precedence,
        ReportRecord.office_precedence,
        ReportRecord.first,
        ReportRecord.last
    ).all()
    grouped = defaultdict(list)
    for record in records:
        grouped[record.name].append(record)
    return {
        "generated": pdf_generator.get_generation_timestamp(),
        "title": "Long Form Roster",
        "grouped": dict(grouped)
    }


def _build_short_roster_data(db: Session) -> Dict[str, Any]:
    records = db.query(ReportRecord).order_by(
        ReportRecord.body_precedence,
        ReportRecord.office_precedence,
        ReportRecord.first,
        ReportRecord.last
    ).all()
    grouped = defaultdict(list)
    for record in records:
        grouped[record.name].append(record)
    return {
        "generated": pdf_generator.get_generation_timestamp(),
        "title": "Short Form Roster",
        "grouped": dict(grouped)
    }


def _build_vacancies_data(db: Session) -> Dict[str, Any]:
    _, grouped = _build_vacancies_dataset(db)
    return {
        "generated": pdf_generator.get_generation_timestamp(),
        "title": "Vacancies",
        "grouped": grouped
    }


def _build_expirations_data(db: Session) -> Dict[str, Any]:
    current_year = datetime.now().year
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

    grouped = defaultdict(list)
    for record in records:
        record.formatted_end = (
            record.end.strftime("%Y-%m-%d") if record.end else ""
        )
        grouped[record.name].append(record)

    return {
        "generated": pdf_generator.get_generation_timestamp(),
        "title": f"Expirations — {current_year}",
        "grouped": dict(grouped)
    }


def _build_terms_report_data(db: Session) -> Dict[str, Any]:
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

    return {
        "generated": pdf_generator.get_generation_timestamp(),
        "title": "Terms with Expiration Dates",
        "rows": rows
    }


# --- Registry ---

REPORT_REGISTRY: Dict[str, ReportRegistryEntry] = {
    "long-roster": ReportRegistryEntry(
        id="long-roster",
        label="Long Form Roster",
        description="Full roster with complete member details",
        filename="long_form_roster.pdf",
        renderer_type="latex_pdf",
        template="lfr_template.tex",
        builder_func=_build_long_roster_data,
    ),
    "short-roster": ReportRegistryEntry(
        id="short-roster",
        label="Short Form Roster",
        description="Condensed roster with names and offices only",
        filename="short_form_roster.pdf",
        renderer_type="latex_pdf",
        template="sfr_template.tex",
        builder_func=_build_short_roster_data,
    ),
    "vacancies": ReportRegistryEntry(
        id="vacancies",
        label="Vacancies",
        description="List of current vacant positions",
        filename="vacancies_report.pdf",
        renderer_type="latex_pdf",
        template="vacancies_template.tex",
        builder_func=_build_vacancies_data,
    ),
    "expirations": ReportRegistryEntry(
        id="expirations",
        label="Expirations",
        description="Terms expiring in the current calendar year",
        filename="expirations_report.pdf",
        renderer_type="latex_pdf",
        template="expirations_template.tex",
        builder_func=_build_expirations_data,
    ),
    "terms-report": ReportRegistryEntry(
        id="terms-report",
        label="Terms Report",
        description="All terms with valid expiration dates",
        filename="terms_report.pdf",
        renderer_type="latex_pdf",
        template="terms_template.tex",
        builder_func=_build_terms_report_data,
    ),
}


# --- Rendering Helpers ---

def _render_pdf_report(report: ReportRegistryEntry, context: Dict[str, Any]) -> FileResponse:
    output_name = report.filename.replace(".pdf", "")
    pdf_path = pdf_generator.generate_pdf(
        template_name=report.template,
        output_name=output_name,
        context=context
    )

    # Special handling for short-roster IONOS publish
    if report.id == "short-roster":
        _publish_short_roster_to_ionos(pdf_path)

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=report.filename,
        headers={"Content-Disposition": f"inline; filename={report.filename}"}
    )


def _publish_short_roster_to_ionos(pdf_path: Path):
    publish_enabled = settings.enable_ionos_roster_publish
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
            logger.exception("IONOS short roster publish failed: %s", exc)
        except Exception as exc:
            logger.exception(
                "IONOS short roster publish failed: unexpected_error=%s",
                exc.__class__.__name__,
            )


def _render_text_report(report: ReportRegistryEntry, emails: List[str]) -> FileResponse:
    report_path = write_email_list_file(pdf_generator.reports_dir, report.filename, emails)
    return FileResponse(
        path=str(report_path),
        media_type="text/plain; charset=utf-8",
        filename=report.filename,
        headers={"Content-Disposition": f"inline; filename={report.filename}"}
    )


@router.get("", response_model=List[ReportMetadata])
async def list_reports():
    """List all available reports with their metadata"""
    return [
        ReportMetadata(
            id=entry.id,
            label=entry.label,
            description=entry.description,
            filename=entry.filename,
            renderer_type=entry.renderer_type
        )
        for entry in REPORT_REGISTRY.values()
    ]


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
        report = REPORT_REGISTRY["long-roster"]
        context = report.builder_func(db)
        return _render_pdf_report(report, context)
    except Exception as e:
        logger.exception("Long roster generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/short-roster")
async def generate_short_roster(db: Session = Depends(get_db)):
    """Generate short form roster (names and offices only)"""
    try:
        report = REPORT_REGISTRY["short-roster"]
        context = report.builder_func(db)
        return _render_pdf_report(report, context)
    except Exception as e:
        logger.exception("Short roster generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vacancies")
async def generate_vacancies_report(db: Session = Depends(get_db)):
    """Generate report of vacant positions"""
    try:
        report = REPORT_REGISTRY["vacancies"]
        context = report.builder_func(db)
        return _render_pdf_report(report, context)
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
        report = REPORT_REGISTRY["expirations"]
        context = report.builder_func(db)
        return _render_pdf_report(report, context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/terms-report")
async def generate_terms_report(db: Session = Depends(get_db)):
    """Generate report of all terms with actual expiration dates"""
    try:
        report = REPORT_REGISTRY["terms-report"]
        context = report.builder_func(db)
        return _render_pdf_report(report, context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rc-officers")
async def generate_rc_officers_email_list(db: Session = Depends(get_db)):
    """Legacy compatibility endpoint for Residents Council officers email list"""
    try:
        report = ReportRegistryEntry(
            id="rc-officers",
            label="Residents Council Officers",
            description="Email list for Residents Council officers",
            filename="rc_officers.txt",
            renderer_type="plain_text_file",
        )
        return _render_text_report(report, get_rc_officers_emails(db))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rc-officers-and-chairs")
async def generate_rc_officers_and_chairs_email_list(db: Session = Depends(get_db)):
    """Legacy compatibility endpoint; now returns committee chairs only"""
    try:
        report = ReportRegistryEntry(
            id="committee-chairs",
            label="Committee Chairs",
            description="Email list for current committee chairs",
            filename="committee_chairs.txt",
            renderer_type="plain_text_file",
        )
        return _render_text_report(report, get_committee_chairs_emails(db))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _get_committee_secretaries_emails(db: Session) -> List[str]:
    return get_committee_secretaries_emails(db)


def _get_hall_reps_emails(db: Session) -> List[str]:
    return get_hall_reps_emails(db)


@router.get("/committee-secretaries")
async def generate_committee_secretaries_email_list(db: Session = Depends(get_db)):
    """Legacy compatibility endpoint for committee secretaries email list"""
    try:
        report = ReportRegistryEntry(
            id="committee-secretaries",
            label="Committee Secretaries",
            description="Email list for current secretaries",
            filename="committee_secretaries.txt",
            renderer_type="plain_text_file",
        )
        return _render_text_report(report, get_committee_secretaries_emails(db))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hall-reps")
async def generate_hall_reps_email_list(db: Session = Depends(get_db)):
    """Legacy compatibility endpoint for hall reps email list"""
    try:
        report = ReportRegistryEntry(
            id="hall-reps",
            label="Hall Reps",
            description="Email list for active hall reps",
            filename="hall_reps.txt",
            renderer_type="plain_text_file",
        )
        return _render_text_report(report, get_hall_reps_emails(db))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
