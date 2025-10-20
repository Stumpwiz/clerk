"""Pydantic schemas for Term (person-to-office assignment) endpoints"""
from typing import Optional
from datetime import date
from pydantic import BaseModel, Field
from pydantic import ConfigDict


class TermBase(BaseModel):
    termpersonid: int
    termofficeid: int
    start: Optional[date] = None
    end: Optional[date] = None
    ordinal: Optional[str] = Field(None, max_length=7)


class TermCreate(TermBase):
    pass


class TermUpdate(BaseModel):
    start: Optional[date] = None
    end: Optional[date] = None
    ordinal: Optional[str] = Field(None, max_length=7)


class TermResponse(TermBase):
    model_config = ConfigDict(from_attributes=True)
