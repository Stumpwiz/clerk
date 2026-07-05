# app/routers/users.py - Local user management

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
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
