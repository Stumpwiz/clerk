"""Pydantic schemas for Term (person-to-office assignment) endpoints"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


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

    class Config:
        from_attributes = True
