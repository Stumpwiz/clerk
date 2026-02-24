# app/routers/letters.py - Operations for LetterTemplate (singleton) and letter generation

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LetterTemplate
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


def sanitize_latex(content: str) -> str:
    """
    Sanitize LaTeX content to ensure it's properly formatted and doesn't contain problematic characters.
    """
    replacements = {
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

    for char, replacement in replacements.items():
        # Replace the character only if it's not preceded by a backslash
        content = re.sub(r'(?<!\\)' + re.escape(char), replacement, content)

    # Ensure proper line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    return content


@router.get("/template", response_model=LetterTemplateResponse)
def get_letter_template(db: Session = Depends(get_db)):
    """Get the letter template (singleton)"""
    template = LetterTemplate.get_singleton(db)
    if not template:
        # Return empty template if none exists
        return LetterTemplateResponse(id=None, header="", body="")
    return template


@router.put("/template", response_model=LetterTemplateResponse)
def update_letter_template(
        template_data: LetterTemplateUpdate,
        db: Session = Depends(get_db)
):
    """Update or create the letter template (singleton)"""
    template = LetterTemplate.get_singleton(db)

    if template:
        # Update existing template
        template.header = template_data.header
        template.body = template_data.body
    else:
        # Create a new template
        template = LetterTemplate(**template_data.model_dump())
        db.add(template)

    db.commit()
    db.refresh(template)
    return template


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

    # Extract last name from recipient (last word)
    last_name = letter_data.recipient.split()[-1] if letter_data.recipient else 'Unknown'

    # Format the letter date
    formatted_letter_date = letter_data.letter_date.strftime('%B %d, %Y').replace(' 0', ' ')
    effective_date_iso = letter_data.letter_date.strftime('%Y-%m-%d')

    # Sanitize input fields
    recipient_safe = sanitize_latex(letter_data.recipient)
    salutation_safe = sanitize_latex(letter_data.salutation)
    apartment_safe = sanitize_latex(letter_data.apartment)

    # Create LaTeX commands for input fields
    recipient_command = f"\\newcommand{{\\names}}{{{recipient_safe}}}"
    salutation_command = f"\\newcommand{{\\salutation}}{{{salutation_safe}}}"
    apartment_command = f"\\newcommand{{\\apartment}}{{{apartment_safe}}}"
    date_command = f"\\date{{{formatted_letter_date}}}"

    # Sanitize template header and body
    header_safe = re.sub(r"(\r\n|\r|\n)+", "\n", template.header.strip())
    body_safe = re.sub(r"(\r\n|\r|\n)+", "\n", template.body.strip())

    # Combine into complete LaTeX document
    tex_content = f"{header_safe}\n{recipient_command}\n{salutation_command}\n{apartment_command}\n{date_command}\n{body_safe}"

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
