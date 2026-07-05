# app/database.py - SQLAlchemy database setup and session management

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.config import settings

# Get database URL from config
DATABASE_URL = settings.database_url

# Create SQLAlchemy engine (PostgreSQL expected)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Helps avoid stale PostgreSQL connections
    echo=settings.debug,
)

# Create SessionLocal class for database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a database session.
    Use this in FastAPI route dependencies to get a DB session.

    Example:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize the database.
    This creates all tables if they don't exist.
    Note: For production, use Alembic migrations instead.
    """
    # Import all models to ensure they're registered with Base
    from app.models import Body, Person, Office, Term, ReportRecord, LetterTemplate, User

    # Create all tables
    Base.metadata.create_all(bind=engine)
