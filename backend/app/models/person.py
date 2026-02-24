# app/models/person.py - An incumbent in a given office.

from sqlalchemy import Column, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Person(Base):
    __tablename__ = 'person'
    __table_args__ = (
        UniqueConstraint('first', 'last', name='uix_person_first_last'),
    )

    person_id = Column('personid', Integer, primary_key=True, autoincrement=True)
    first = Column(String(15), nullable=True, default=None)
    last = Column(String(30), nullable=True, default=None)
    email = Column(String(45), nullable=True, default=None)
    phone = Column(String(19), nullable=True, default=None)
    apt = Column(String(4), nullable=True, default=None)

    # Relationships
    terms = relationship("Term", back_populates="person", lazy=True)

    def __repr__(self):
        return f'<Person {self.first} {self.last}>'
