# app/models/__init__.py - Export all models

from app.models.body import Body
from app.models.person import Person
from app.models.office import Office
from app.models.term import Term
from app.models.report_record import ReportRecord
from app.models.letters import LetterTemplate

__all__ = [
    "Body",
    "Person",
    "Office",
    "Term",
    "ReportRecord",
    "LetterTemplate",
]
