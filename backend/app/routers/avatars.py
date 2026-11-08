"""Session-owned avatars; raw bodies avoid multipart parsing and spooling."""
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import require_authenticated_user
from app.avatars import MAX_UPLOAD_BYTES, normalize_avatar
from app.database import get_db
from app.models import User
from app.routers.auth import UserResponse

router = APIRouter(tags=["avatars"])


async def bounded_image(request: Request) -> bytes:
    length = request.headers.get("content-length")
    if length is not None:
        try:
            size = int(length)
        except ValueError as exc:
            raise HTTPException(400, "Invalid Content-Length") from exc
        if size < 0:
            raise HTTPException(400, "Invalid Content-Length")
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Avatar exceeds 2 MiB")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Avatar exceeds 2 MiB")
        data.extend(chunk)
    return bytes(data)


def save_avatar(db: Session, user: User, data: bytes | None) -> UserResponse:
    path = f"/api/avatars/{user.id}/{uuid4().hex}.png" if data is not None else None
    try:
        db.execute(update(User).where(User.id == user.id).values(
            avatar_bytes=data, avatar_path=path,
        ))
        db.flush()
        db.refresh(user)
        result = UserResponse.model_validate(user)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.put("/api/auth/me/avatar", response_model=UserResponse)
async def upload_avatar(
    request: Request,
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    data = await bounded_image(request)
    normalized = await run_in_threadpool(normalize_avatar, data)
    return await run_in_threadpool(save_avatar, db, current_user, normalized)


@router.delete("/api/auth/me/avatar", response_model=UserResponse)
def remove_avatar(
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    return save_avatar(db, current_user, None)


@router.get("/api/avatars/{user_id}/{revision}.png")
def get_avatar(
    user_id: int,
    revision: str,
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    if user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(403, "Avatar access denied")
    path = f"/api/avatars/{user_id}/{revision}.png"
    data = db.scalar(select(User.avatar_bytes).where(
        User.id == user_id, User.avatar_path == path,
    ))
    if data is None:
        raise HTTPException(404, "Avatar not found")
    return Response(data, media_type="image/png", headers={
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })
