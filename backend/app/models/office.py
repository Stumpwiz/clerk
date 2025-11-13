# app/models/office.py - An area of responsibility for a given body.

from sqlalchemy import Column, Integer, String, Float, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Office(Base):
    __tablename__ = 'office'

    office_id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(45), nullable=True, default=None)
    office_precedence = Column(Float, nullable=True, default=None)
    office_body_id = Column(BigInteger, ForeignKey('body.body_id'), nullable=False)

    # Relationships
    body = relationship("Body", back_populates="offices")
    terms = relationship("Term", back_populates="office", lazy=True)

    def __repr__(self):
        return f'<Office {self.title}>'
