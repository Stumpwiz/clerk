"""Local authentication endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.cookies import clear_session_cookie, set_session_cookie
from app.auth.dependencies import require_authenticated_user
from app.auth.passwords import verify_password
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    avatar_path: str | None = None
    is_active: bool
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    user: UserResponse


class LogoutResponse(BaseModel):
    success: bool


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, response: Response, db: Session = Depends(get_db)):
    normalized_email = request.email.lower()
    user = db.scalar(select(User).where(func.lower(User.email) == normalized_email))

    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    set_session_cookie(response, user.id)
    return LoginResponse(user=UserResponse.model_validate(user))


@router.post("/logout", response_model=LogoutResponse)
def logout(response: Response):
    clear_session_cookie(response)
    return LogoutResponse(success=True)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(require_authenticated_user)):
    return UserResponse.model_validate(current_user)
