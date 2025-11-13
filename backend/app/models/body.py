# app/models/body.py - An administrative body that comprises various offices.

from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import relationship
from app.database import Base


class Body(Base):
    __tablename__ = 'body'

    body_id = Column(Integer, primary_key=True)
    name = Column(String(45), nullable=False)
    mission = Column(String(512), nullable=True, default=None)
    body_precedence = Column(
        Float, 
        nullable=False,
        comment="Used for ordering in reports and on web pages"
    )

    # Relationships
    offices = relationship("Office", back_populates="body", lazy=True)

    def __repr__(self):
        return f'<Body {self.name}>'
