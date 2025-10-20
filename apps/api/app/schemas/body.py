"""Pydantic schemas for Body (committee/organization) endpoints"""
from typing import Optional
from pydantic import BaseModel, Field
from pydantic import ConfigDict


class BodyBase(BaseModel):
    name: str = Field(..., max_length=45)
    mission: Optional[str] = Field(None, max_length=512)
    body_precedence: float


class BodyCreate(BodyBase):
    pass


class BodyUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=45)
    mission: Optional[str] = Field(None, max_length=512)
    body_precedence: Optional[float] = None


class BodyResponse(BodyBase):
    body_id: int

    model_config = ConfigDict(from_attributes=True)
