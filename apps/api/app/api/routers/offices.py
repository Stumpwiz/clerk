"""API router for Office (position) CRUD operations"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.base import get_db
from app.db.models import Office
from app.schemas.office import OfficeCreate, OfficeUpdate, OfficeResponse
from app.security.auth import get_authorized_user, AuthorizedUser

router = APIRouter(prefix="/offices", tags=["offices"])


@router.get("", response_model=List[OfficeResponse])
def list_offices(
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Get all offices ordered by office_precedence within body"""
    offices = (
        db.query(Office)
        .order_by(Office.office_body_id, Office.office_precedence)
        .all()
    )
    return offices


@router.get("/{office_id}", response_model=OfficeResponse)
def get_office(
    office_id: int,
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Get a single office by ID"""
    office = db.query(Office).filter(Office.office_id == office_id).first()
    if not office:
        raise HTTPException(status_code=404, detail="Office not found")
    return office


@router.post("", response_model=OfficeResponse, status_code=status.HTTP_201_CREATED)
def create_office(
    office_data: OfficeCreate,
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Create a new office"""
    office = Office(**office_data.model_dump())
    db.add(office)
    db.commit()
    db.refresh(office)
    return office


@router.put("/{office_id}", response_model=OfficeResponse)
def update_office(
    office_id: int,
    office_data: OfficeUpdate,
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Update an existing office"""
    office = db.query(Office).filter(Office.office_id == office_id).first()
    if not office:
        raise HTTPException(status_code=404, detail="Office not found")

    update_data = office_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(office, field, value)

    db.commit()
    db.refresh(office)
    return office


@router.delete("/{office_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_office(
    office_id: int,
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Delete an office"""
    office = db.query(Office).filter(Office.office_id == office_id).first()
    if not office:
        raise HTTPException(status_code=404, detail="Office not found")

    db.delete(office)
    db.commit()
    return None
