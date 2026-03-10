# app/schemas/letter.py - Pydantic schemas for LetterTemplate model

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class LetterTemplateUpdate(BaseModel):
    """Schema for updating the letter template"""
    body: str = Field(..., description="Plain text body of the welcome letter")


class LetterTemplateResponse(BaseModel):
    """Schema for LetterTemplate responses"""
    id: Optional[int] = None
    body: str

    class Config:
        from_attributes = True


class LetterGenerateRequest(BaseModel):
    """Schema for generating a welcome letter"""
    letter_date: date = Field(..., description="Date to appear on the letter")
    recipient: str = Field(..., description="Recipient name(s), e.g., 'John and Mary Smith'")
    salutation: str = Field(..., description="Salutation without 'Dear', e.g., 'John and Mary'")
    apartment: str = Field(..., description="Apartment number")


class LetterGenerateResponse(BaseModel):
    """Response after generating a letter"""
    success: bool
    filename: Optional[str] = None
    error: Optional[str] = None


class PDFFileInfo(BaseModel):
    """Information about a PDF file"""
    filename: str
    date_prefix: Optional[str] = None
