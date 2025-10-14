from fastapi import APIRouter, Depends
from app.security.auth import get_authorized_user, AuthorizedUser
from app.schemas.user import UserResponse

router = APIRouter()


@router.get("/test")
async def test_endpoint():
    """Simple test endpoint with no authentication"""
    return {"status": "success", "message": "Auth router is working"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """
    Get current authenticated and authorized user information.
    
    Returns user details including role from database.
    Requires valid Clerk JWT and email must exist in users table.
    """
    return UserResponse(
        user_id=current_user.clerk_user_id,
        email=current_user.email,
        username=current_user.username,
        role=current_user.role,
    )


# Temporary simplified version for testing
@router.get("/me-simple")
async def get_me_simple():
    """Simplified endpoint to test routing without authentication"""
    return {
        "status": "endpoint_reached",
        "message": "This endpoint works without authentication",
    }
