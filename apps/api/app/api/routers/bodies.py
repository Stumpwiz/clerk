"""API router for Body (committee/organization) CRUD operations"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.base import get_db
from app.db.models import Body
from app.schemas.body import BodyCreate, BodyUpdate, BodyResponse
from app.security.auth import get_authorized_user, AuthorizedUser

router = APIRouter(prefix="/bodies", tags=["bodies"])


@router.get("", response_model=List[BodyResponse])
def list_bodies(
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Get all bodies ordered by precedence"""
    bodies = db.query(Body).order_by(Body.body_precedence).all()
    return bodies


@router.get("/{body_id}", response_model=BodyResponse)
def get_body(
    body_id: int,
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Get a single body by ID"""
    body = db.query(Body).filter(Body.body_id == body_id).first()
    if not body:
        raise HTTPException(status_code=404, detail="Body not found")
    return body


@router.post("", response_model=BodyResponse, status_code=status.HTTP_201_CREATED)
def create_body(
    body_data: BodyCreate,
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Create a new body"""
    body = Body(**body_data.model_dump())
    db.add(body)
    db.commit()
    db.refresh(body)
    return body


@router.put("/{body_id}", response_model=BodyResponse)
def update_body(
    body_id: int,
    body_data: BodyUpdate,
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Update an existing body"""
    body = db.query(Body).filter(Body.body_id == body_id).first()
    if not body:
        raise HTTPException(status_code=404, detail="Body not found")

    update_data = body_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(body, field, value)

    db.commit()
    db.refresh(body)
    return body


@router.delete("/{body_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_body(
    body_id: int,
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Delete a body"""
    body = db.query(Body).filter(Body.body_id == body_id).first()
    if not body:
        raise HTTPException(status_code=404, detail="Body not found")

    db.delete(body)
    db.commit()
    return None
