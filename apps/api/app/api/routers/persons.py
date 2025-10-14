"""API router for Person (community member) CRUD operations"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.base import get_db
from app.db.models import Person
from app.schemas.person import PersonCreate, PersonUpdate, PersonResponse
from app.security.auth import get_authorized_user, AuthorizedUser

router = APIRouter(prefix="/persons", tags=["persons"])


@router.get("", response_model=List[PersonResponse])
def list_persons(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Get all persons ordered by last name"""
    persons = (
        db.query(Person)
        .order_by(Person.last, Person.first)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return persons


@router.get("/{person_id}", response_model=PersonResponse)
def get_person(
    person_id: int,
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Get a single person by ID"""
    person = db.query(Person).filter(Person.personid == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


@router.post("", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
def create_person(
    person_data: PersonCreate,
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Create a new person"""
    person = Person(**person_data.model_dump())
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


@router.put("/{person_id}", response_model=PersonResponse)
def update_person(
    person_id: int,
    person_data: PersonUpdate,
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Update an existing person"""
    person = db.query(Person).filter(Person.personid == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    update_data = person_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(person, field, value)

    db.commit()
    db.refresh(person)
    return person


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(
    person_id: int,
    db: Session = Depends(get_db),
    current_user: AuthorizedUser = Depends(get_authorized_user)
):
    """Delete a person"""
    person = db.query(Person).filter(Person.personid == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    db.delete(person)
    db.commit()
    return None
