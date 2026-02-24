# app/models/report_record.py - Read-only SQLAlchemy model mapped to the report_record view
# This view is used for all roster and report generation

from sqlalchemy import Column, Integer, String, Date, Float
from app.database import Base


class ReportRecord(Base):
    __tablename__ = 'report_record'
    __table_args__ = {'extend_existing': True}

    person_id = Column(Integer)
    first = Column(String)
    last = Column(String)
    email = Column(String)
    phone = Column(String)
    apt = Column(String)
    start = Column(Date)
    end = Column(Date)
    ordinal = Column(String)
    term_person_id = Column(Integer, primary_key=True)
    term_office_id = Column(Integer, primary_key=True)
    office_id = Column(Integer)
    title = Column(String)
    office_precedence = Column(Float)
    office_body_id = Column(Integer)
    body_id = Column(Integer)
    name = Column(String)
    body_precedence = Column(Float)

    def __repr__(self):
        return f'<ReportRecord {self.name} - {self.title} - {self.first} {self.last}>'
