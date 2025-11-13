# app/schemas/office.py - Pydantic schemas for the Office model

from pydantic import BaseModel, Field
from typing import Optional


class OfficeBase(BaseModel):
    """Base schema with common Office fields"""
    title: Optional[str] = Field(None, max_length=45, description="Office title")
    office_precedence: Optional[float] = Field(None, description="Used for ordering")
    office_body_id: int = Field(..., description="ID of the body this office belongs to")


class OfficeCreate(OfficeBase):
    """Schema for creating a new Office"""
    pass


class OfficeUpdate(BaseModel):
    """Schema for updating an Office (all fields optional)"""
    title: Optional[str] = Field(None, max_length=45)
    office_precedence: Optional[float] = None
    office_body_id: Optional[int] = None


class OfficeResponse(BaseModel):
    """Schema for Office responses"""
    office_id: int
    title: Optional[str]
    office_precedence: Optional[float]
    office_body_id: int

    class Config:
        from_attributes = True
