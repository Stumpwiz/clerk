"""
Set max_incumbents=1 for common single-incumbent officer roles.

Usage:
  cd apps/api
  python set_office_max_incumbents.py
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models import Office

SINGLE_INCUMBENT_TITLES = [
    "President",
    "Vice President",
    "Secretary",
    "Treasurer",
    # Add more titles here as needed
]


def main():
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        updated = 0
        for title in SINGLE_INCUMBENT_TITLES:
            offices = session.query(Office).filter(Office.title == title).all()
            for o in offices:
                if o.max_incumbents != 1:
                    o.max_incumbents = 1
                    updated += 1
        session.commit()
        print(f"Updated {updated} office(s) to max_incumbents=1.")
    except Exception as e:
        session.rollback()
        print(f"Error updating offices: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
