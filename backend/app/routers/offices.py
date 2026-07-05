# app/routers/offices.py - CRUD operations for Office resources

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.auth.dependencies import require_authenticated_user
from app.database import get_db
from app.models import Office
from app.schemas.office import OfficeCreate, OfficeUpdate, OfficeResponse

router = APIRouter(
    prefix="/api/offices",
    tags=["Offices"],
    dependencies=[Depends(require_authenticated_user)],
)


@router.get("", response_model=List[OfficeResponse])
def get_offices(db: Session = Depends(get_db)):
    """Get all offices"""
    offices = db.query(Office).order_by(Office.office_precedence).all()
    return offices


@router.get("/{office_id}", response_model=OfficeResponse)
def get_office(office_id: int, db: Session = Depends(get_db)):
    """Get a specific office by ID"""
    office = db.query(Office).filter(Office.office_id == office_id).first()
    if not office:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Office with id {office_id} not found"
        )
    return office


@router.post("", response_model=OfficeResponse, status_code=status.HTTP_201_CREATED)
def create_office(office_data: OfficeCreate, db: Session = Depends(get_db)):
    """Create a new office"""
    office = Office(**office_data.model_dump())
    db.add(office)
    db.commit()
    db.refresh(office)
    return office


@router.put("/{office_id}", response_model=OfficeResponse)
def update_office(office_id: int, office_data: OfficeUpdate, db: Session = Depends(get_db)):
    """Update an existing office"""
    office = db.query(Office).filter(Office.office_id == office_id).first()
    if not office:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Office with id {office_id} not found"
        )

    # Update only provided fields
    update_data = office_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(office, field, value)

    db.commit()
    db.refresh(office)
    return office


@router.delete("/{office_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_office(office_id: int, db: Session = Depends(get_db)):
    """Delete an office"""
    office = db.query(Office).filter(Office.office_id == office_id).first()
    if not office:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Office with id {office_id} not found"
        )

    db.delete(office)
    db.commit()
    return None
