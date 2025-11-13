# app/schemas/term.py - Pydantic schemas for the Term model

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class TermBase(BaseModel):
    """Base schema with common Term fields"""
    term_person_id: int = Field(..., description="Person ID")
    term_office_id: int = Field(..., description="Office ID")
    start: Optional[date] = Field(None, description="Start date of term")
    end: Optional[date] = Field(None, description="End date of term")
    ordinal: Optional[str] = Field(None, max_length=7, description="Ordinal (e.g., '1st', '2nd')")


class TermCreate(TermBase):
    """Schema for creating a new Term"""
    pass


class TermUpdate(BaseModel):
    """Schema for updating a Term (non-key fields only)"""
    start: Optional[date] = None
    end: Optional[date] = None
    ordinal: Optional[str] = Field(None, max_length=7)


class TermResponse(TermBase):
    """Schema for Term responses"""

    class Config:
        from_attributes = True
