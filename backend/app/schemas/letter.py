# app/schemas/letter.py - Pydantic schemas for LetterTemplate model

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date
from datetime import date


class LetterTemplateUpdate(BaseModel):
    """Schema for updating the letter template"""
    header: str = Field(..., description="Letter header text")
    body: str = Field(..., description="Letter body text")


class LetterTemplateResponse(BaseModel):
    """Schema for LetterTemplate responses"""
    id: Optional[int] = None
    header: str
    body: str

    class Config:
        from_attributes = True


class LetterGenerateRequest(BaseModel):
    """Schema for generating a letter"""
    recipient: str = Field(..., description="Recipient name(s)")
    salutation: str = Field(..., description="Salutation for the letter")
    apartment: str = Field(..., description="Apartment number")
    letter_date: date = Field(..., description="Date to appear on the letter")


class LetterGenerateResponse(BaseModel):
    """Schema for letter generation response"""
    success: bool
    filename: Optional[str] = None
    error: Optional[str] = None


class PDFFileInfo(BaseModel):
    """Schema for PDF file information"""
    filename: str
    date_prefix: Optional[str] = None


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
