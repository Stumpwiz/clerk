# app/schemas/__init__.py - Export all schemas

from app.schemas.body import BodyCreate, BodyUpdate, BodyResponse
from app.schemas.office import OfficeCreate, OfficeUpdate, OfficeResponse
from app.schemas.person import PersonCreate, PersonUpdate, PersonResponse
from app.schemas.term import TermCreate, TermUpdate, TermResponse
from app.schemas.letter import LetterTemplateUpdate, LetterTemplateResponse

__all__ = [
    "BodyCreate",
    "BodyUpdate",
    "BodyResponse",
    "OfficeCreate",
    "OfficeUpdate",
    "OfficeResponse",
    "PersonCreate",
    "PersonUpdate",
    "PersonResponse",
    "TermCreate",
    "TermUpdate",
    "TermResponse",
    "LetterTemplateUpdate",
    "LetterTemplateResponse",
]
