# app/routers/letters.py - Operations for LetterTemplate (singleton) and letter generation

import os
import re
import subprocess
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LetterTemplate, ReportRecord
from app.schemas.letter import (
    LetterTemplateUpdate,
    LetterTemplateResponse,
    LetterGenerateRequest,
    LetterGenerateResponse,
    PDFFileInfo
)

# Determine base directory for file storage
BASE_DIR = Path(__file__).resolve().parent.parent.parent
FILES_LETTERS_DIR = BASE_DIR / "files_letters"
STATIC_IMAGES_DIR = BASE_DIR / "static" / "images"

# Ensure directories exist
FILES_LETTERS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/api/letters", tags=["Letters"])


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
    body_latex = convert_plain_text_to_latex(body_text)
    signer_name_safe = escape_latex(signer_name)
    signer_apt_safe = escape_latex(signer_apt)

    # Build the complete LaTeX document
    latex_doc = f"""\\documentclass[11pt,letterpaper]{{article}}
\\usepackage{{geometry}}
\\usepackage{{graphicx}}
\\usepackage{{fontspec}}
\\usepackage{{setspace}}

\\geometry{{
    letterpaper,
    left=1in,
    right=1in,
    top=1in,
    bottom=1in
}}

\\setmainfont{{TeX Gyre Termes}}
\\pagestyle{{empty}}
\\setstretch{{1.15}}

\\newcommand{{\\names}}{{{recipient_safe}}}
\\newcommand{{\\salutation}}{{{salutation_safe}}}
\\newcommand{{\\apartment}}{{{apartment_safe}}}
\\date{{{letter_date_str}}}

\\begin{{document}}

\\begin{{center}}
    \\includegraphics[width=1.5in]{{../static/images/residentCouncilLogoSmall.jpg}} \\\\[0.5em]
\\end{{center}}

\\vspace{{1em}}

\\noindent \\today

\\vspace{{1em}}

\\noindent \\names \\\\
Apartment \\apartment

\\vspace{{1em}}

\\noindent Dear \\salutation,

\\vspace{{0.5em}}

{body_latex}

\\vspace{{1.5em}}

\\noindent Sincerely,

\\vspace{{2em}}

\\noindent {signer_name_safe} \\\\
President, Residents Council \\\\
Apartment {signer_apt_safe}

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
    last_name = letter_data.recipient.split()[-1] if letter_data.recipient else 'Unknown'

    # Format the letter date
    formatted_letter_date = letter_data.letter_date.strftime('%B %d, %Y').replace(' 0', ' ')
    effective_date_iso = letter_data.letter_date.strftime('%Y-%m-%d')

    # Build the complete LaTeX document
    tex_content = build_latex_document(
        recipient=letter_data.recipient,
        salutation=letter_data.salutation,
        apartment=letter_data.apartment,
        letter_date_str=formatted_letter_date,
        body_text=template.body,
        signer_name=signer_name,
        signer_apt=signer_apt
    )

    # Build filename
    safe_base = f"{effective_date_iso}_{last_name}" if last_name else f"{effective_date_iso}"

    try:
        # Create the .tex file
        tex_file_path = FILES_LETTERS_DIR / f"{safe_base}.tex"
        with open(tex_file_path, 'w', encoding='utf-8') as tex_file:
            tex_file.write(tex_content)

        # Path to output PDF
        pdf_path = FILES_LETTERS_DIR / f"{safe_base}.pdf"

        # Run xelatex - need to run it twice for proper page numbering and references
        for run in range(2):
            result = subprocess.run(
                ["xelatex", "-interaction=nonstopmode", "-output-directory", str(FILES_LETTERS_DIR),
                 str(tex_file_path)],
                cwd=str(FILES_LETTERS_DIR),
                capture_output=True,
                text=True,
                timeout=30
            )

        # Check if compilation succeeded and PDF was generated
        if result.returncode == 0 and pdf_path.exists():
            # Verify PDF is not empty (has reasonable size)
            pdf_size = pdf_path.stat().st_size
            if pdf_size < 1000:  # PDF should be at least 1KB
                return LetterGenerateResponse(
                    success=False,
                    error="PDF file was generated but appears to be corrupted or empty"
                )

            # Clean up LaTeX auxiliary files including .tex source
            aux_extensions = ['.tex', '.aux', '.log', '.out', '.toc', '.lof', '.lot', '.fls', '.fdb_latexmk',
                              '.synctex.gz', '.dvi']
            for file in FILES_LETTERS_DIR.glob(f"{safe_base}.*"):
                if file.suffix in aux_extensions:
                    try:
                        file.unlink()
                    except Exception:
                        pass

            return LetterGenerateResponse(success=True, filename=f"{safe_base}.pdf")
        else:
            error_msg = "Failed to generate PDF. Check LaTeX template and logs."
            if result.returncode != 0:
                # Check for LaTeX errors in stdout
                if "! " in result.stdout:
                    error_lines = [line for line in result.stdout.split('\n') if "! " in line]
                    if error_lines:
                        error_msg = f"LaTeX error: {error_lines[0].strip()}"
            return LetterGenerateResponse(success=False, error=error_msg)

    except subprocess.TimeoutExpired:
        return LetterGenerateResponse(success=False, error="LaTeX compilation timed out")
    except Exception as e:
        return LetterGenerateResponse(success=False, error=f"Unexpected error: {str(e)}")


@router.get("/pdfs", response_model=List[PDFFileInfo])
def list_pdfs():
    """List all generated PDF files"""
    if not FILES_LETTERS_DIR.exists():
        return []

    # Gather all PDF files
    all_pdfs = [f.name for f in FILES_LETTERS_DIR.glob("*.pdf")]

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


@router.get("/pdfs/{filename}")
def view_pdf(filename: str):
    """View a specific PDF file"""
    pdf_path = FILES_LETTERS_DIR / filename

    # Security: ensure filename doesn't contain path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename"
        )

    if not pdf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF file {filename} not found"
        )

    # Return FileResponse without filename parameter to display inline
    # Set Content-Disposition to inline for browser viewing
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )


@router.delete("/pdfs/{filename}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pdf(filename: str):
    """Delete a specific PDF file"""
    pdf_path = FILES_LETTERS_DIR / filename

    # Security: ensure filename doesn't contain path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename"
        )

    if not pdf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF file {filename} not found"
        )

    try:
        pdf_path.unlink()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting PDF: {str(e)}"
        )

    return None
