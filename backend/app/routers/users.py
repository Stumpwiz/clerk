# app/routers/users.py - Local user management

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_authenticated_user
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


@router.get("/list", response_model=List[UserListItem])
async def list_users(db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.display_name, User.email)).all()
    return [UserListItem.model_validate(user) for user in users]
