# app/routers/letters.py - Operations for LetterTemplate (singleton) and letter generation

import shutil
from tempfile import TemporaryDirectory
from urllib.parse import quote
import re
import subprocess
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_authenticated_user
from app.database import get_db
from app.models import LetterTemplate, ReportRecord, GeneratedLetter
from app.letter_storage import save_generated_pdf, validate_filename
from app.schemas.letter import (
    LetterTemplateUpdate,
    LetterTemplateResponse,
    LetterGenerateRequest,
    LetterGenerateResponse,
    PDFFileInfo
)

# Determine base directory for file storage
BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_IMAGES_DIR = BASE_DIR / "static" / "images"


router = APIRouter(
    prefix="/api/letters",
    tags=["Letters"],
    dependencies=[Depends(require_authenticated_user)],
)


def escape_latex(text: str) -> str:
    """
    Escape special LaTeX characters in plain text for safe inclusion in LaTeX documents.
    """
    replacements = {
        '\\': '\\textbackslash{}',
        '&': '\\&',
        '%': '\\%',
        '$': '\\$',
        '#': '\\#',
        '_': '\\_',
        '{': '\\{',
        '}': '\\}',
        '~': '\\textasciitilde{}',
        '^': '\\textasciicircum{}',
    }

    result = text
    for char, replacement in replacements.items():
        result = result.replace(char, replacement)

    return result


def convert_plain_text_to_latex(plain_text: str) -> str:
    """
    Convert plain text body to LaTeX, preserving paragraphs and escaping special characters.
    """
    # Normalize line endings
    text = plain_text.replace('\r\n', '\n').replace('\r', '\n')

    # Split into paragraphs (separated by blank lines)
    paragraphs = re.split(r'\n\s*\n', text.strip())

    # Escape each paragraph and join with LaTeX paragraph breaks
    latex_paragraphs = [escape_latex(p.strip()) for p in paragraphs if p.strip()]

    return '\n\n'.join(latex_paragraphs)


def get_current_rc_president(db: Session) -> Optional[tuple[str, str]]:
    """
    Query the ReportRecord to find the current Residents Council President.
    Returns (full_name, apartment) or None if not found.
    """
    today = date.today()

    # Query for current RC President
    query = db.query(ReportRecord).filter(
        ReportRecord.name == "Residents Council",
        ReportRecord.title == "President"
    )

    # Try to find active term (start <= today, end is null or >= today)
    active = query.filter(
        ReportRecord.start <= today,
        (ReportRecord.end.is_(None)) | (ReportRecord.end >= today)
    ).first()

    if active:
        full_name = f"{active.first or ''} {active.last or ''}".strip()
        return (full_name, active.apt or '')

    # Fallback: get the most recent record
    recent = query.order_by(ReportRecord.start.desc()).first()

    if recent:
        full_name = f"{recent.first or ''} {recent.last or ''}".strip()
        return (full_name, recent.apt or '')

    return None


def build_latex_document(
    *,
    recipient: str,
    salutation: str,
    apartment: str,
    street: Optional[str],
    city_state_zip: Optional[str],
    letter_date_str: str,
    body_text: str,
    signer_name: str,
    signer_apt: str
) -> str:
    """
    Build a complete LaTeX document from the provided components.
    All inputs except body_text should already be LaTeX-safe.
    """
    # Escape user inputs
    recipient_safe = escape_latex(recipient)
    salutation_safe = escape_latex(salutation)
    apartment_safe = escape_latex(apartment)
    street_safe = escape_latex(street) if street else None
    city_state_zip_safe = escape_latex(city_state_zip) if city_state_zip else None
    body_latex = convert_plain_text_to_latex(body_text)
    signer_name_safe = escape_latex(signer_name)
    signer_apt_safe = escape_latex(signer_apt)

    # Build inside address block
    address_lines = [f"{recipient_safe}"]
    if apartment_safe:
        address_lines.append(f"Apartment {apartment_safe}")
    if street_safe:
        address_lines.append(street_safe)
    if city_state_zip_safe:
        address_lines.append(city_state_zip_safe)
    inside_address = " \\\\\n".join(address_lines)

    # Tunable layout constants for letter visual formatting
    logo_width_in = 2.25
    logo_top_offset_in = -0.10
    # Position measured from left text block edge (1in page margin),
    # equivalent to 4.5in from physical page left edge.
    right_anchor_from_text_left_in = 3.5
    paragraph_indent = "2em"
    paragraph_spacing = "1.0\\baselineskip"

    # Build the complete LaTeX document
    latex_doc = f"""\\documentclass[11pt,letterpaper]{{article}}
\\usepackage{{geometry}}
\\usepackage{{graphicx}}
\\usepackage{{setspace}}

\\geometry{{
    letterpaper,
    left=1in,
    right=1in,
    top=1.30in,
    bottom=1in
}}

\\pagestyle{{empty}}
\\setstretch{{1.0}}
\\setlength{{\\parindent}}{{{paragraph_indent}}}
\\setlength{{\\parskip}}{{{paragraph_spacing}}}

\\newcommand{{\\salutation}}{{{salutation_safe}}}
\\date{{{letter_date_str}}}

\\begin{{document}}

\\vspace*{{{logo_top_offset_in}in}}
\\begin{{center}}
    \\includegraphics[width={logo_width_in}in]{{residentCouncilLogoSmall.jpg}} \\\\[0.5em]
\\end{{center}}

\\vspace{{0.6em}}

\\noindent\\hspace*{{{right_anchor_from_text_left_in}in}}{letter_date_str}

\\vspace{{1em}}

\\noindent {inside_address}

\\vspace{{1.0em}}

\\noindent Dear \\salutation,

\\vspace{{0.5em}}

{body_latex}

\\vspace{{1.0em}}

\\noindent\\hspace*{{{right_anchor_from_text_left_in}in}}\\parbox[t]{{2.6in}}{{%
Sincerely,\\\\[2\\baselineskip]
{signer_name_safe} \\\\
President, Residents Council \\\\
Apartment {signer_apt_safe}
}}


\\end{{document}}"""

    return latex_doc


@router.get("/template", response_model=LetterTemplateResponse)
def get_letter_template(db: Session = Depends(get_db)):
    """Get the letter template (singleton)"""
    template = LetterTemplate.get_singleton(db)
    if not template:
        # Return empty template if none exists
        return LetterTemplateResponse(id=None, body="")
    return LetterTemplateResponse(id=template.id, body=template.body)


@router.put("/template", response_model=LetterTemplateResponse)
def update_letter_template(
        template_data: LetterTemplateUpdate,
        db: Session = Depends(get_db)
):
    """Update or create the letter template (singleton)"""
    template = LetterTemplate.get_singleton(db)

    if template:
        # Update existing template
        template.body = template_data.body
        # Keep header empty or preserve existing value for backward compatibility
        if not hasattr(template, 'header') or template.header is None:
            template.header = ""
    else:
        # Create a new template
        template = LetterTemplate(header="", body=template_data.body)
        db.add(template)

    db.commit()
    db.refresh(template)
    return LetterTemplateResponse(id=template.id, body=template.body)


@router.post("/generate", response_model=LetterGenerateResponse)
def generate_letter(
        letter_data: LetterGenerateRequest,
        db: Session = Depends(get_db)
):
    """Generate a welcome letter PDF using LaTeX"""
    # Get the template
    template = LetterTemplate.get_singleton(db)
    if not template:
        return LetterGenerateResponse(
            success=False,
            error="No template found. Please create a template first."
        )

    # Get the current RC President
    president_info = get_current_rc_president(db)
    if not president_info:
        return LetterGenerateResponse(
            success=False,
            error="Could not find Residents Council President in database."
        )

    signer_name, signer_apt = president_info

    # Extract last name from recipient (last word)
    last_name = letter_data.recipient.split()[-1] if letter_data.recipient.split() else 'Unknown'

    # Format the letter date
    formatted_letter_date = letter_data.letter_date.strftime('%B %d, %Y').replace(' 0', ' ')
    effective_date_iso = letter_data.letter_date.strftime('%Y-%m-%d')

    # Defaults for street and city/state/ZIP
    street = letter_data.street.strip() if letter_data.street and letter_data.street.strip() else "2525 Pot Spring Road"
    city_state_zip = letter_data.city_state_zip.strip() if letter_data.city_state_zip and letter_data.city_state_zip.strip() else "Timonium MD 21093"

    # Build the complete LaTeX document
    tex_content = build_latex_document(
        recipient=letter_data.recipient,
        salutation=letter_data.salutation,
        apartment=letter_data.apartment,
        street=street,
        city_state_zip=city_state_zip,
        letter_date_str=formatted_letter_date,
        body_text=template.body,
        signer_name=signer_name,
        signer_apt=signer_apt
    )

    # Build filename
    safe_base = f"{effective_date_iso}_{last_name}" if last_name else f"{effective_date_iso}"

    filename = f"{safe_base}.pdf"
    try:
        validate_filename(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        with TemporaryDirectory(prefix="clerk-letter-") as work_dir:
            work = Path(work_dir)
            # A fixed working name avoids user-controlled paths and LaTeX arguments.
            tex_file = work / "letter.tex"
            tex_file.write_text(tex_content, encoding="utf-8")
            shutil.copyfile(STATIC_IMAGES_DIR / "residentCouncilLogoSmall.jpg",
                            work / "residentCouncilLogoSmall.jpg")
            for _ in range(2):
                result = subprocess.run(
                    ["xelatex", "-interaction=nonstopmode", "-halt-on-error",
                     "-no-shell-escape", "letter.tex"],
                    cwd=work, capture_output=True, text=True, timeout=30,
                )
                if result.returncode != 0:
                    return LetterGenerateResponse(success=False, error="Failed to generate PDF.")
            pdf_path = work / "letter.pdf"
            if not pdf_path.exists():
                return LetterGenerateResponse(success=False, error="Failed to generate PDF.")
            data = pdf_path.read_bytes()
            if len(data) < 1000 or not data.startswith(b"%PDF-"):
                return LetterGenerateResponse(success=False, error="Generated PDF is invalid or empty.")
            save_generated_pdf(db, filename, data)
            db.commit()
        return LetterGenerateResponse(success=True, filename=filename)
    except subprocess.TimeoutExpired:
        db.rollback()
        return LetterGenerateResponse(success=False, error="LaTeX compilation timed out")
    except Exception:
        db.rollback()
        # Do not expose database parameters (including PDF bytes) in errors.
        return LetterGenerateResponse(success=False, error="Unable to generate or save the PDF. Please retry.")


@router.get("/pdfs", response_model=List[PDFFileInfo])
def list_pdfs(db: Session = Depends(get_db)):
    """List all generated PDF files"""
    # Select metadata only; do not load PDF blobs for the list.
    all_pdfs = db.scalars(select(GeneratedLetter.filename).order_by(
        GeneratedLetter.created_at, GeneratedLetter.filename)).all()

    # Partition into dated and undated
    dated = []
    undated = []
    date_prefix_re = re.compile(r'^(\d{4}-\d{2}-\d{2})_')

    for fname in all_pdfs:
        m = date_prefix_re.match(fname)
        if m:
            date_str = m.group(1)
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d').date()
                dated.append((dt, fname, date_str))
            except ValueError:
                undated.append(fname)
        else:
            undated.append(fname)

    # Sort dated ascending, undated alphabetically
    dated.sort(key=lambda t: t[0])
    undated.sort()

    # Build result list with PDFFileInfo objects
    result = []
    for dt, fname, date_str in dated:
        result.append(PDFFileInfo(filename=fname, date_prefix=date_str))
    for fname in undated:
        result.append(PDFFileInfo(filename=fname, date_prefix=None))

    return result


def checked_filename(filename: str) -> str:
    try:
        validate_filename(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filename


@router.get("/pdfs/{filename}")
def view_pdf(filename: str, db: Session = Depends(get_db)):
    letter = db.get(GeneratedLetter, checked_filename(filename))
    if letter is None:
        raise HTTPException(status_code=404, detail=f"PDF file {filename} not found")
    return Response(
        content=letter.pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(filename, safe='')}",
                 "Cache-Control": "private, no-store"},
    )


@router.delete("/pdfs/{filename}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pdf(filename: str, db: Session = Depends(get_db)):
    letter = db.get(GeneratedLetter, checked_filename(filename))
    if letter is None:
        raise HTTPException(status_code=404, detail=f"PDF file {filename} not found")
    try:
        db.delete(letter)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to delete PDF") from exc
    return Response(status_code=204)
