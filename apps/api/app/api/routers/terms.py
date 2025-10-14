"""API router for Term (person-to-office assignment) CRUD operations"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.base import get_db
from app.db.models import Term
from app.schemas.term import TermCreate, TermUpdate, TermResponse
from app.security.auth import get_authorized_user, AuthorizedUser

router = APIRouter(prefix="/terms", tags=["terms"])


@router.get("", response_model=List[TermResponse])
def list_terms(
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Get all terms"""
    terms = db.query(Term).all()
    return terms


@router.get("/{person_id}/{office_id}", response_model=TermResponse)
def get_term(
    person_id: int,
    office_id: int,
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Get a single term by composite key"""
    term = (
        db.query(Term)
        .filter(Term.termpersonid == person_id, Term.termofficeid == office_id)
        .first()
    )
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")
    return term


@router.post("", response_model=TermResponse, status_code=status.HTTP_201_CREATED)
def create_term(
    term_data: TermCreate,
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Create a new term"""
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
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Update an existing term (dates/ordinal only)"""
    term = (
        db.query(Term)
        .filter(Term.termpersonid == person_id, Term.termofficeid == office_id)
        .first()
    )
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")

    update_data = term_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(term, field, value)

    db.commit()
    db.refresh(term)
    return term


@router.delete("/{person_id}/{office_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_term(
    person_id: int,
    office_id: int,
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Delete a term by composite key"""
    term = (
        db.query(Term)
        .filter(Term.termpersonid == person_id, Term.termofficeid == office_id)
        .first()
    )
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")

    db.delete(term)
    db.commit()
    return None
