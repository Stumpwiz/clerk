# app/schemas/body.py - Pydantic schemas for the Body model

from pydantic import BaseModel, Field
from typing import Optional


class BodyBase(BaseModel):
    """Base schema with common Body fields"""
    name: str = Field(..., max_length=45, description="Name of the administrative body")
    mission: Optional[str] = Field(None, max_length=512, description="Mission statement")
    body_precedence: float = Field(..., description="Used for ordering in reports and web pages")


class BodyCreate(BodyBase):
    """Schema for creating a new Body"""
    pass


class BodyUpdate(BaseModel):
    """Schema for updating a Body (all fields optional)"""
    name: Optional[str] = Field(None, max_length=45)
    mission: Optional[str] = Field(None, max_length=512)
    body_precedence: Optional[float] = None


class BodyResponse(BodyBase):
    """Schema for Body responses"""
    body_id: int

    class Config:
        from_attributes = True
