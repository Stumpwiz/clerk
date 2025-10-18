"""API router for report generation"""
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List
from pathlib import Path
from datetime import datetime
import os
import re

from ...db.base import get_db
from ...security.auth import get_current_user, ClerkUser
from ...services.reports_service import generate_expirations_report, generate_vacancies_report

router = APIRouter(prefix="/reports", tags=["reports"]) 

SAFE_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _reports_dir() -> Path:
    """Get the reports output directory (same as roster_output_dir)."""
    from ...core.config import settings
    return Path(settings.roster_output_dir)


@router.post("/generate/expirations")
async def generate_expirations_pdf(
    days: int = Query(90, description="Number of days to look ahead"),
    db: Session = Depends(get_db),
    current_user: ClerkUser = Depends(get_current_user)
):
    """Generate expirations report PDF."""
    result = generate_expirations_report(db, days)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to generate expirations report"))
    return result


@router.post("/generate/vacancies")
async def generate_vacancies_pdf(
    db: Session = Depends(get_db),
    current_user: ClerkUser = Depends(get_current_user)
):
    """Generate vacancies report PDF."""
    result = generate_vacancies_report(db)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to generate vacancies report"))
    return result


@router.get("/list")
async def list_reports(
    current_user: ClerkUser = Depends(get_current_user)
):
    """List all generated report PDFs."""
    directory = _reports_dir()
    files_info: List[dict] = []

    if not directory.exists():
        return {"files": []}

    try:
        # Look for files with pattern: YYYY-MM-DD_report_*.pdf
        for pdf in sorted(directory.glob("*_report_*.pdf")):
            try:
                stat = pdf.stat()
                files_info.append({
                    "name": pdf.name,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
                })
            except OSError:
                continue
    except Exception:
        return {"files": []}

    return {"files": files_info}


@router.get("/download/{filename}")
async def download_report(
    filename: str,
    current_user: ClerkUser = Depends(get_current_user)
):
    """Download a specific report PDF."""
    # Validate filename for safety
    if not SAFE_FILENAME_PATTERN.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    path = _reports_dir() / filename

    if not path.exists() or path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )


@router.delete("/{filename}")
async def delete_report(
    filename: str,
    db: Session = Depends(get_db),
    current_user: ClerkUser = Depends(get_current_user)
):
    """Delete a report PDF and its corresponding TEX file."""
    # Validate filename
    if not SAFE_FILENAME_PATTERN.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    directory = _reports_dir()
    pdf_path = directory / filename

    if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="File not found")

    # Attempt deletion of PDF and corresponding TEX
    errors = []
    try:
        os.remove(pdf_path)
    except OSError as e:
        errors.append(str(e))

    base = pdf_path.with_suffix("")  # remove .pdf
    tex_path = base.with_suffix(".tex")
    if tex_path.exists():
        try:
            os.remove(tex_path)
        except OSError:
            pass  # Non-fatal

    if errors:
        raise HTTPException(status_code=500, detail="; ".join(errors))

    return {"success": True, "message": "Report deleted successfully"}


@router.get("/vacancy")
def vacancy_report(
    db: Session = Depends(get_db),
    current_user: ClerkUser = Depends(get_current_user)
):
    """Generate vacancy report - offices without current assignments"""
    query = text(
        """
            SELECT 
                body.name as body_name,
                office.title as office_title,
                office.office_precedence
            FROM office
            JOIN body ON body.body_id = office.office_body_id
            LEFT JOIN term ON term.termofficeid = office.office_id 
                AND (term.end IS NULL OR term.end > date('now'))
            WHERE term.termpersonid IS NULL
            ORDER BY body.body_precedence, office.office_precedence
        """
    )
    result = db.execute(query)
    vacancies = [dict(row._mapping) for row in result]
    return {"vacancies": vacancies, "count": len(vacancies)}


@router.get("/expiring-terms")
def expiring_terms_report(
    days: int = Query(90, description="Number of days to look ahead"),
    db: Session = Depends(get_db),
    current_user: ClerkUser = Depends(get_current_user)
):
    """Generate expiring terms report"""
    query = text(
        """
            SELECT 
                person.first,
                person.last,
                person.email,
                body.name as body_name,
                office.title as office_title,
                term.end as term_end_date
            FROM term
            JOIN person ON person.personid = term.termpersonid
            JOIN office ON office.office_id = term.termofficeid
            JOIN body ON body.body_id = office.office_body_id
            WHERE term.end IS NOT NULL 
                AND term.end <= date('now', '+' || :days || ' days')
                AND term.end >= date('now')
            ORDER BY term.end, body.body_precedence
        """
    )
    result = db.execute(query, {"days": days})
    expiring = [dict(row._mapping) for row in result]
    return {"expiring_terms": expiring, "count": len(expiring), "days_ahead": days}


@router.get("/full-roster")
def full_roster_report(
    db: Session = Depends(get_db),
    current_user: ClerkUser = Depends(get_current_user)
):
    """Generate full roster from report_record view"""
    query = text("SELECT * FROM report_record")
    result = db.execute(query)
    roster = [dict(row._mapping) for row in result]
    return {"roster": roster, "count": len(roster)}
