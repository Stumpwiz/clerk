# app/models/term.py - The tenure of a given person in a given office.
# This is the junction table that resolves the many-to-many relationship between persons and offices.

from sqlalchemy import Column, Integer, Date, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Term(Base):
    __tablename__ = 'term'

    # Composite primary key
    term_person_id = Column(
        'termpersonid', 
        Integer, 
        ForeignKey('person.personid'), 
        primary_key=True
    )
    term_office_id = Column(
        'termofficeid', 
        Integer, 
        ForeignKey('office.office_id'), 
        primary_key=True
    )

    # Other fields
    start = Column(Date, nullable=True, default=None)
    end = Column(Date, nullable=True, default=None)
    ordinal = Column(String(7), nullable=True, default=None)

    # Relationships
    person = relationship("Person", back_populates="terms")
    office = relationship("Office", back_populates="terms")

    def __repr__(self):
        return f'<Term {self.term_person_id}-{self.term_office_id}>'
