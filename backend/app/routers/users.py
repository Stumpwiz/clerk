# app/routers/users.py - Local user management

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import require_authenticated_user
from app.auth.passwords import hash_password
from app.database import get_db
from app.models import User

router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    dependencies=[Depends(require_authenticated_user)],
)


class UserListItem(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    avatar_path: str | None = None
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserCreateRequest(BaseModel):
    email: EmailStr
    display_name: str
    password: str
    is_active: bool = True

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        trimmed_value = value.strip()
        if not trimmed_value:
            raise ValueError("Display name is required")
        return trimmed_value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value:
            raise ValueError("Password is required")
        return value


class UserUpdateRequest(BaseModel):
    display_name: str
    is_active: bool

    model_config = ConfigDict(extra="forbid")

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        trimmed_value = value.strip()
        if not trimmed_value:
            raise ValueError("Display name is required")
        return trimmed_value


class UserPasswordResetRequest(BaseModel):
    new_password: str

    model_config = ConfigDict(extra="forbid")


@router.get("/list", response_model=List[UserListItem])
async def list_users(db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.display_name, User.email)).all()
    return [UserListItem.model_validate(user) for user in users]


@router.post("", response_model=UserListItem, status_code=status.HTTP_201_CREATED)
def create_user(request: UserCreateRequest, db: Session = Depends(get_db)):
    normalized_email = request.email.lower()
    existing_user = db.scalar(select(User).where(func.lower(User.email) == normalized_email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        email=normalized_email,
        display_name=request.display_name,
        password_hash=hash_password(request.password),
        is_active=request.is_active,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from exc

    db.refresh(user)
    return UserListItem.model_validate(user)


@router.put("/{user_id}", response_model=UserListItem)
def update_user(user_id: int, request: UserUpdateRequest, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found",
        )

    user.display_name = request.display_name
    user.is_active = request.is_active
    db.commit()
    db.refresh(user)
    return UserListItem.model_validate(user)


@router.post("/{user_id}/reset-password")
def reset_user_password(user_id: int, request: UserPasswordResetRequest, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found",
        )

    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters",
        )

    user.password_hash = hash_password(request.new_password)
    db.commit()
    return {"success": True}


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=403, detail="You cannot delete your own account.")

    # Refresh even an existing ORM identity, and serialize with concurrent updates.
    user = db.scalar(select(User).where(User.id == user_id).with_for_update()
                     .execution_options(populate_existing=True))
    if user is None:
        raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")
    if user.is_active:
        raise HTTPException(status_code=409,
                            detail="This user must first be made inactive before deletion.")
    try:
        db.delete(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409,
                            detail="This user cannot be deleted because related records exist.") from exc
    return Response(status_code=204)
