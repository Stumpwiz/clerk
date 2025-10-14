from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from .base import Base


# Body model (committees/organizations)
class Body(Base):
    __tablename__ = "body"

    body_id = Column(Integer, primary_key=True)
    name = Column(String(45), nullable=False)
    mission = Column(String(512))
    body_precedence = Column(Float, nullable=False)

    # Relationships
    offices = relationship("Office", back_populates="body")


# Office model (positions within bodies)
class Office(Base):
    __tablename__ = "office"

    office_id = Column(Integer, primary_key=True)
    title = Column(String(45))
    office_precedence = Column(Float)
    office_body_id = Column(Integer, ForeignKey("body.body_id"), nullable=False)

    # Relationships
    body = relationship("Body", back_populates="offices")
    terms = relationship("Term", back_populates="office")


# Person model (community members)
class Person(Base):
    __tablename__ = "person"

    personid = Column(Integer, primary_key=True)
    first = Column(String(15))
    last = Column(String(30))
    email = Column(String(45))
    phone = Column(String(19))
    apt = Column(String(4))

    __table_args__ = (
        UniqueConstraint("first", "last", name="uix_person_first_last"),
    )

    # Relationships
    terms = relationship("Term", back_populates="person")


# Term model (junction table - person assignments to offices)
class Term(Base):
    __tablename__ = "term"

    termpersonid = Column(Integer, ForeignKey("person.personid"), primary_key=True)
    termofficeid = Column(Integer, ForeignKey("office.office_id"), primary_key=True)
    start = Column(Date)
    end = Column(Date)
    ordinal = Column(String(7))

    # Relationships
    person = relationship("Person", back_populates="terms")
    office = relationship("Office", back_populates="terms")


# Letter model (LaTeX templates)
class Letter(Base):
    __tablename__ = "letters"

    id = Column(Integer, primary_key=True)
    header = Column(Text, nullable=False)
    body = Column(Text, nullable=False)


# User model (authorization - stores who has access and their role)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(45), nullable=False)
    email = Column(String(100), nullable=False, unique=True, index=True)
    role = Column(String(20), nullable=False, default="user")  # "admin" or "user"

    __table_args__ = (
        UniqueConstraint("email", name="uix_user_email"),
    )
