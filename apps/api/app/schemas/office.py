"""Pydantic schemas for Office (position) endpoints"""
from typing import Optional
from pydantic import BaseModel, Field
from pydantic import ConfigDict


class OfficeBase(BaseModel):
    title: Optional[str] = Field(None, max_length=45)
    office_precedence: Optional[float] = None
    office_body_id: int
    max_incumbents: Optional[int] = Field(
        default=None,
        description="Maximum concurrent incumbents allowed; NULL/None means unlimited, 1 means single-incumbent"
    )


class OfficeCreate(OfficeBase):
    pass


class OfficeUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=45)
    office_precedence: Optional[float] = None
    office_body_id: Optional[int] = None
    max_incumbents: Optional[int] = Field(
        default=None,
        description="Maximum concurrent incumbents allowed; NULL/None means unlimited, 1 means single-incumbent"
    )


class OfficeResponse(OfficeBase):
    office_id: int

    model_config = ConfigDict(from_attributes=True)
