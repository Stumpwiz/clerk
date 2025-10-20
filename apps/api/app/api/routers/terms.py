"""API router for Term (person-to-office assignment) CRUD operations"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date as _date

from app.db.base import get_db
from app.db.models import Term, Office
from app.schemas.term import TermCreate, TermUpdate, TermResponse
from app.security.auth import get_authorized_user, AuthorizedUser

router = APIRouter(prefix="/terms", tags=["terms"])


def _as_min(d: Optional[_date]) -> _date:
    return d if d is not None else _date.min


def _as_max(d: Optional[_date]) -> _date:
    return d if d is not None else _date.max


def _overlaps(a_start: Optional[_date], a_end: Optional[_date], b_start: Optional[_date], b_end: Optional[_date]) -> bool:
    """
    Half-open interval overlap: [start, end)
    NULL start = -infinity, NULL end = +infinity
    Overlap if not (a_end <= b_start or b_end <= a_start)
    """
    a_s, a_e = _as_min(a_start), _as_max(a_end)
    b_s, b_e = _as_min(b_start), _as_max(b_end)
    return not (a_e <= b_s or b_e <= a_s)


def _enforce_office_cap(
    db: Session,
    office_id: int,
    new_start: Optional[_date],
    new_end: Optional[_date],
    exclude_person_id: Optional[int] = None,
) -> None:
    """
    If Office.max_incumbents is set (>0), ensure no more than that many terms overlap
    with the proposed [new_start, new_end) interval for the given office.
    """
    office = db.query(Office).filter(Office.office_id == office_id).first()
    if not office:
        raise HTTPException(status_code=404, detail="Office not found")

    cap = office.max_incumbents or 0
    if cap <= 0:
        return  # unlimited: no enforcement

    # Count overlaps among existing terms for this office (excluding a specific person if requested)
    q = db.query(Term).filter(Term.termofficeid == office_id)
    if exclude_person_id is not None:
        q = q.filter(Term.termpersonid != exclude_person_id)
    existing = q.all()

    overlap_count = 0
    for t in existing:
        if _overlaps(t.start, t.end, new_start, new_end):
            overlap_count += 1

    # For create: adding one more would exceed if overlap_count >= cap
    # For update (excluding the current term): after update, existing overlaps + 1 (self) would exceed if overlap_count >= cap
    if overlap_count >= cap:
        if cap == 1:
            raise HTTPException(
                status_code=400,
                detail="This office already has an overlapping term. End the existing term or adjust dates before adding another."
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"This office allows at most {cap} overlapping incumbents. Your change would exceed that."
            )


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
    # Enforce max_incumbents overlap rule for the destination office
    _enforce_office_cap(
        db=db,
        office_id=term_data.termofficeid,
        new_start=term_data.start,
        new_end=term_data.end,
        exclude_person_id=None,
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

    # Determine proposed interval after update
    new_start = term_data.start if term_data.start is not None else term.start
    new_end = term_data.end if term_data.end is not None else term.end

    # Enforce max_incumbents overlap rule (exclude the current term's person id)
    _enforce_office_cap(
        db=db,
        office_id=office_id,
        new_start=new_start,
        new_end=new_end,
        exclude_person_id=person_id,
    )

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
