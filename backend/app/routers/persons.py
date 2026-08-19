# app/routers/persons.py - CRUD operations for Person resources

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List

from app.auth.dependencies import require_authenticated_user
from app.database import get_db
from app.models import Person
from app.schemas.person import PersonCreate, PersonUpdate, PersonResponse

router = APIRouter(
    prefix="/api/persons",
    tags=["Persons"],
    dependencies=[Depends(require_authenticated_user)],
)

PERSON_NAME_UNIQUE_CONSTRAINT = "uix_person_first_last"


def _is_duplicate_person_error(exc: IntegrityError) -> bool:
    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint_name == PERSON_NAME_UNIQUE_CONSTRAINT:
        return True

    # SQLite does not expose named constraints, but is used by focused API tests.
    return str(exc.orig) == "UNIQUE constraint failed: person.first, person.last"


@router.get("", response_model=List[PersonResponse])
def get_persons(db: Session = Depends(get_db)):
    """Get all persons"""
    persons = db.query(Person).order_by(Person.last, Person.first).all()
    return persons


@router.get("/{person_id}", response_model=PersonResponse)
def get_person(person_id: int, db: Session = Depends(get_db)):
    """Get a specific person by ID"""
    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Person with id {person_id} not found"
        )
    return person


@router.post("", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
def create_person(person_data: PersonCreate, db: Session = Depends(get_db)):
    """Create a new person"""
    person = Person(**person_data.model_dump())
    db.add(person)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if not _is_duplicate_person_error(exc):
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A person with this first and last name already exists",
        ) from exc
    db.refresh(person)
    return person


@router.put("/{person_id}", response_model=PersonResponse)
def update_person(person_id: int, person_data: PersonUpdate, db: Session = Depends(get_db)):
    """Update an existing person"""
    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Person with id {person_id} not found"
        )

    # Update only provided fields
    update_data = person_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(person, field, value)

    db.commit()
    db.refresh(person)
    return person


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(person_id: int, db: Session = Depends(get_db)):
    """Delete a person"""
    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Person with id {person_id} not found"
        )

    db.delete(person)
    db.commit()
    return None
