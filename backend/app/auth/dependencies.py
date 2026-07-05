"""FastAPI dependencies for local authentication."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.cookies import parse_session_cookie_value
from app.config import settings
from app.database import get_db
from app.models import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    cookie_value = request.cookies.get(settings.session_cookie_name)
    user_id = parse_session_cookie_value(cookie_value)
    if user_id is None:
        return None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def require_authenticated_user(
    current_user: User | None = Depends(get_current_user),
) -> User:
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return current_user
