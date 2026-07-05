# app/routers/terms.py - CRUD operations for Term resources

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.auth.dependencies import require_authenticated_user
from app.database import get_db
from app.models import Term
from app.schemas.term import TermCreate, TermUpdate, TermResponse

router = APIRouter(
    prefix="/api/terms",
    tags=["Terms"],
    dependencies=[Depends(require_authenticated_user)],
)


@router.get("", response_model=List[TermResponse])
def get_terms(db: Session = Depends(get_db)):
    """Get all terms"""
    terms = db.query(Term).all()
    return terms


@router.get("/{person_id}/{office_id}", response_model=TermResponse)
def get_term(person_id: int, office_id: int, db: Session = Depends(get_db)):
    """Get a specific term by composite key (person_id, office_id)"""
    term = db.query(Term).filter(
        Term.term_person_id == person_id,
        Term.term_office_id == office_id
    ).first()
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Term for person {person_id} and office {office_id} not found"
        )
    return term


@router.post("", response_model=TermResponse, status_code=status.HTTP_201_CREATED)
def create_term(term_data: TermCreate, db: Session = Depends(get_db)):
    """Create a new term"""
    # Check if the term already exists
    existing = db.query(Term).filter(
        Term.term_person_id == term_data.term_person_id,
        Term.term_office_id == term_data.term_office_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Term already exists for this person and office"
        )

    term = Term(**term_data.model_dump())
    db.add(term)
    db.commit()
    db.refresh(term)
    return term


@router.put("/{person_id}/{office_id}", response_model=TermResponse)
def update_term(
    person_id: int,
    office_id: int,
    term_data: TermUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing term (only non-key fields can be updated)"""
    term = db.query(Term).filter(
        Term.term_person_id == person_id,
        Term.term_office_id == office_id
    ).first()
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Term for person {person_id} and office {office_id} not found"
        )

    # Update only provided fields (excluding primary keys)
    update_data = term_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(term, field, value)

    db.commit()
    db.refresh(term)
    return term


@router.delete("/{person_id}/{office_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_term(person_id: int, office_id: int, db: Session = Depends(get_db)):
    """Delete a term"""
    term = db.query(Term).filter(
        Term.term_person_id == person_id,
        Term.term_office_id == office_id
    ).first()
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Term for person {person_id} and office {office_id} not found"
        )

    db.delete(term)
    db.commit()
    return None
