# app/routers/__init__.py - Export all routers

from app.routers import auth, bodies, offices, persons, terms, letters, reports, users, mailing_lists, help

__all__ = [
    "auth",
    "bodies",
    "offices",
    "persons",
    "terms",
    "letters",
    "reports",
    "users",
    "mailing_lists",
    "help",
]
