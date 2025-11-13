# app/models/letters.py - Letter template for welcome letters to new residents

from sqlalchemy import Column, Integer, Text
from sqlalchemy.orm import Session
from app.database import Base


class LetterTemplate(Base):
    __tablename__ = 'letters'

    id = Column(Integer, primary_key=True)
    header = Column(Text, nullable=False)
    body = Column(Text, nullable=False)

    @staticmethod
    def get_singleton(db: Session):
        """
        Fetch the single letter template record, or None if not present.
        """
        return db.query(LetterTemplate).first()

    @staticmethod
    def can_add_record(db: Session) -> bool:
        """
        Return True if the table is empty, i.e., no template exists yet.
        """
        return db.query(LetterTemplate).count() == 0

    def __repr__(self):
        return f'<LetterTemplate {self.id}>'
