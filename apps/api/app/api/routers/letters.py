from pathlib import Path
from typing import List
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import get_db
from app.db.models import Letter
from app.schemas.letter import LetterTemplateResponse, LetterTemplateUpdate
from app.security.auth import get_authorized_user, AuthorizedUser
from app.services.pdf_service import generate_pdf, list_pdfs, delete_pdf

router = APIRouter(prefix="/letters", tags=["letters"]) 


class LetterGenerateRequest(BaseModel):
    addressee: str = Field(..., min_length=1, max_length=200)
    salutation: str = Field(..., min_length=1, max_length=100)
    date: str = Field(default="", description="Date in YYYY-MM-DD format, defaults to today")
    apartment: str = Field(..., pattern=r"^[KLS][1-7](0[1-9]|[1-3][0-9]|4[0-4])$")


class LetterGenerateResponse(BaseModel):
    success: bool
    filename: str | None = None
    error: str | None = None


class PDFListItem(BaseModel):
    filename: str
    created: str
    size: int


@router.get("/template", response_model=LetterTemplateResponse)
async def get_template(
    db: Session = Depends(get_db),
    user: AuthorizedUser = Depends(get_authorized_user)
):
    """
    Get the current letter template (header and body).
    Accessible to all authenticated users.
    """
    template = db.query(Letter).first()
    
    if not template:
        raise HTTPException(
            status_code=404,
            detail="No letter template found. Please contact administrator."
        )
    
    return template


@router.put("/template", response_model=LetterTemplateResponse)
async def update_template(
    template_data: LetterTemplateUpdate,
    db: Session = Depends(get_db),
    user: AuthorizedUser = Depends(get_authorized_user)
):
    """
    Update the letter template (header and body).
    Accessible to all authenticated users.
    """
    template = db.query(Letter).first()
    
    if not template:
        # Create if doesn't exist (should not happen with proper migration)
        template = Letter(header=template_data.header, body=template_data.body)
        db.add(template)
    else:
        template.header = template_data.header
        template.body = template_data.body
    
    db.commit()
    db.refresh(template)
    
    return template


@router.post("/generate", response_model=LetterGenerateResponse)
async def generate_letter(
    request: LetterGenerateRequest,
    db: Session = Depends(get_db),
    user: AuthorizedUser = Depends(get_authorized_user)
):
    """
    Generate a PDF welcome letter with the provided parameters.
    Accessible to all authenticated users.
    """
    # Get template
    template = db.query(Letter).first()
    
    if not template:
        raise HTTPException(
            status_code=404,
            detail="No letter template found"
        )
    
    # Generate PDF
    result = generate_pdf(
        header=template.header,
        body=template.body,
        addressee=request.addressee,
        salutation=request.salutation,
        date_str=request.date,
        apartment=request.apartment
    )
    
    return result


@router.get("/pdfs", response_model=List[PDFListItem])
async def list_letters(
    user: AuthorizedUser = Depends(get_authorized_user)
):
    """
    List all generated PDF letters.
    Accessible to all authenticated users.
    """
    pdfs = list_pdfs()
    return pdfs


@router.get("/pdfs/{filename}")
async def get_pdf(
    filename: str,
    user: AuthorizedUser = Depends(get_authorized_user)
):
    """
    Download/view a generated PDF letter.
    Accessible to all authenticated users.
    """
    # Security check
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    pdf_path = Path(settings.pdf_output_dir) / filename
    
    if not pdf_path.exists() or pdf_path.suffix != ".pdf":
        raise HTTPException(status_code=404, detail="PDF not found")
    
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )


@router.delete("/pdfs/{filename}")
async def delete_letter(
    filename: str,
    user: AuthorizedUser = Depends(get_authorized_user)
):
    """
    Delete a generated PDF letter.
    Accessible to all authenticated users.
    """
    success = delete_pdf(filename)
    
    if not success:
        raise HTTPException(status_code=404, detail="PDF not found or could not be deleted")
    
    return {"success": True, "message": f"Deleted {filename}"}
