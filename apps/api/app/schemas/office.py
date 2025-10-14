"""Pydantic schemas for Office (position) endpoints"""
from pydantic import BaseModel, Field
from typing import Optional


class OfficeBase(BaseModel):
    title: Optional[str] = Field(None, max_length=45)
    office_precedence: Optional[float] = None
    office_body_id: int


class OfficeCreate(OfficeBase):
    pass


class OfficeUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=45)
    office_precedence: Optional[float] = None
    office_body_id: Optional[int] = None


class OfficeResponse(OfficeBase):
    office_id: int

    class Config:
        from_attributes = True
