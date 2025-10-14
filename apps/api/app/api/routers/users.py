from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.base import get_db
from app.db.models import User
from app.security.auth import require_admin, AuthorizedUser
from app.schemas.user_management import (
    UserInvite,
    UserUpdate,
    UserListResponse,
    UserInviteResponse,
)

router = APIRouter()


@router.get("/", response_model=List[UserListResponse])
async def list_users(
    admin_user: AuthorizedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    List all authorized users (admin only).
    
    Returns list of users with their roles, ordered by username.
    """
    users = db.query(User).order_by(User.username).all()
    return users


@router.post("/", response_model=UserInviteResponse, status_code=status.HTTP_201_CREATED)
async def invite_user(
    user_data: UserInvite,
    admin_user: AuthorizedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Invite a new user by adding them to the authorized users table (admin only).
    
    The user will be able to sign in with Clerk once their email is authorized.
    """
    # Check if user already exists
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email {user_data.email} already exists",
        )
    
    # Create new user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        role=user_data.role,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return UserInviteResponse(
        message=f"User {user_data.username} successfully invited",
        user=UserListResponse.model_validate(new_user),
    )


@router.put("/{user_id}", response_model=UserListResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    admin_user: AuthorizedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Update user information (admin only).
    
    Can update username and/or role.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )
    
    # Prevent admin from demoting themselves
    if user.email == admin_user.email and user_data.role == "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot demote yourself from admin role",
        )
    
    # Update fields if provided
    if user_data.username is not None:
        user.username = user_data.username
    if user_data.role is not None:
        user.role = user_data.role
    
    db.commit()
    db.refresh(user)
    
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_user_access(
    user_id: int,
    admin_user: AuthorizedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Revoke user access by removing them from authorized users (admin only).
    
    The user will no longer be able to access the API.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )
    
    # Prevent admin from deleting themselves
    if user.email == admin_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    
    db.delete(user)
    db.commit()
    
    return None
