from pydantic import BaseModel


class UserResponse(BaseModel):
    """Response schema for current user information"""
    user_id: str  # Clerk user ID
    email: str
    username: str
    role: str
    
    class Config:
        from_attributes = True
