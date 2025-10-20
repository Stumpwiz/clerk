"""Pydantic schemas for Person (community member) endpoints"""
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from pydantic import ConfigDict


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


auto_trim = True  # local toggle to trim string fields


class PersonBase(BaseModel):
    # Optional fields (nullable in DB)
    first: Optional[str] = Field(None, max_length=15)
    last: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=45)
    phone: Optional[str] = Field(None, max_length=19)
    apt: Optional[str] = Field(None, max_length=4)

    @field_validator("email", mode="before")
    @classmethod
    def email_blank_to_none(cls, v):
        return _blank_to_none(v)

    @field_validator("first", "last", "phone", "apt", mode="before")
    @classmethod
    def trim_text_fields(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
        return v


class PersonCreate(BaseModel):
    # Require first and last on creation; others optional
    first: str = Field(..., max_length=15)
    last: str = Field(..., max_length=30)
    email: Optional[str] = Field(None, max_length=45)
    phone: Optional[str] = Field(None, max_length=19)
    apt: Optional[str] = Field(None, max_length=4)

    @field_validator("email", mode="before")
    @classmethod
    def email_blank_to_none_create(cls, v):
        return _blank_to_none(v)

    @field_validator("first", "last", "phone", "apt", mode="before")
    @classmethod
    def trim_text_fields_create(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
        return v


class PersonUpdate(BaseModel):
    # All fields optional for partial update
    first: Optional[str] = Field(None, max_length=15)
    last: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=45)
    phone: Optional[str] = Field(None, max_length=19)
    apt: Optional[str] = Field(None, max_length=4)

    @field_validator("email", mode="before")
    @classmethod
    def email_blank_to_none_update(cls, v):
        return _blank_to_none(v)

    @field_validator("first", "last", "phone", "apt", mode="before")
    @classmethod
    def trim_text_fields_update(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
        return v


class PersonResponse(BaseModel):
    personid: int
    first: Optional[str] = Field(None, max_length=15)
    last: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=45)
    phone: Optional[str] = Field(None, max_length=19)
    apt: Optional[str] = Field(None, max_length=4)

    @field_validator("email", mode="before")
    @classmethod
    def email_blank_to_none_response(cls, v):
        return _blank_to_none(v)

    # Pydantic v2 config to serialize from ORM models
    model_config = ConfigDict(from_attributes=True)
