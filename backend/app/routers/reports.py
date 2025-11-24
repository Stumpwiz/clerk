# app/routers/reports.py - API endpoints for roster and report generation

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List

from app.database import get_db
from app.models import ReportRecord
from app.utils.pdf_generator import PDFGenerator

router = APIRouter(prefix="/api/reports", tags=["reports"])

# Initialize PDF generator
pdf_generator = PDFGenerator()


@router.get("/pdfs", response_model=List[dict])
async def list_report_pdfs():
    """List all available report PDF files"""
    try:
        pdf_files = []
        reports_dir = pdf_generator.reports_dir

        if reports_dir.exists():
            for pdf_file in reports_dir.glob("*.pdf"):
                pdf_files.append({
                    "filename": pdf_file.name,
                    "size": pdf_file.stat().st_size,
                    "modified": pdf_file.stat().st_mtime
                })

        # Sort by filename
        pdf_files.sort(key=lambda x: x["filename"])
        return pdf_files

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdfs/{filename}")
async def serve_report_pdf(filename: str):
    """Serve a specific report PDF file"""
    try:
        # Security: Only allow PDF files and prevent path traversal
        if not filename.endswith(".pdf") or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        pdf_path = pdf_generator.reports_dir / filename

        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="PDF not found")

        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
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

        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename="short_form_roster.pdf",
            headers={"Content-Disposition": "inline; filename=short_form_roster.pdf"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vacancies")
async def generate_vacancies_report(db: Session = Depends(get_db)):
    """Generate report of vacant positions"""
    try:
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

        # Generate PDF
        context = {
            "generated": pdf_generator.get_generation_timestamp(),
            "title": "Vacancies",
            "grouped": dict(grouped)
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
