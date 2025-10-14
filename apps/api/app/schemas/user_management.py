from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UserInvite(BaseModel):
    """Schema for inviting a new user"""
    email: EmailStr
    username: str = Field(..., min_length=1, max_length=45)
    role: str = Field(..., pattern="^(admin|user)$")


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    username: Optional[str] = Field(None, min_length=1, max_length=45)
    role: Optional[str] = Field(None, pattern="^(admin|user)$")


class UserListResponse(BaseModel):
    """Schema for user list item"""
    id: int
    username: str
    email: str
    role: str
    
    class Config:
        from_attributes = True


class UserInviteResponse(BaseModel):
    """Schema for successful user invitation"""
    message: str
    user: UserListResponse
