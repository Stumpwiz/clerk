# app/schemas/person.py - Pydantic schemas for the Person model

from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class PersonBase(BaseModel):
    """Base schema with common Person fields"""
    first: Optional[str] = Field(None, max_length=15, description="First name")
    last: Optional[str] = Field(None, max_length=30, description="Last name")
    email: Optional[str] = Field(None, max_length=45, description="Email address")
    phone: Optional[str] = Field(None, max_length=19, description="Phone number")
    apt: Optional[str] = Field(None, max_length=4, description="Apartment number")


class PersonCreate(PersonBase):
    """Schema for creating a new Person"""
    pass


class PersonUpdate(BaseModel):
    """Schema for updating a Person (all fields optional)"""
    first: Optional[str] = Field(None, max_length=15)
    last: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=45)
    phone: Optional[str] = Field(None, max_length=19)
    apt: Optional[str] = Field(None, max_length=4)


class PersonResponse(PersonBase):
    """Schema for Person responses"""
    person_id: int

    class Config:
        from_attributes = True
