"""Pydantic schemas for Person (community member) endpoints"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class PersonBase(BaseModel):
    first: Optional[str] = Field(None, max_length=15)
    last: Optional[str] = Field(None, max_length=30)
    email: Optional[EmailStr] = Field(None, max_length=45)
    phone: Optional[str] = Field(None, max_length=19)
    apt: Optional[str] = Field(None, max_length=4)


class PersonCreate(PersonBase):
    pass


class PersonUpdate(PersonBase):
    pass


class PersonResponse(PersonBase):
    personid: int

    class Config:
        from_attributes = True
