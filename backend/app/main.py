# app/main.py - FastAPI application entry point

from contextlib import asynccontextmanager
from typing import List
from urllib.parse import urlparse

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ReportRecord

# Import routers
from app.routers import auth, bodies, offices, persons, terms, letters, reports, users, mailing_lists


def _db_host_and_name(database_url: str) -> tuple[str, str]:
    parsed = urlparse(database_url) if database_url else None
    if not parsed:
        return ("", "")
    db_name = parsed.path.lstrip("/") if parsed.path else ""
    return (parsed.hostname or "", db_name)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    print(f"*** {settings.app_name} started ***")
    db_host, db_name = _db_host_and_name(settings.database_url)
    print(f"Database: host={db_host} name={db_name}")
    print(f"API Docs: http://{settings.api_host}:{settings.api_port}/docs")
    yield
    # Shutdown (if needed in the future)
    print("Shutting down...")


# Create FastAPI application
app = FastAPI(
    title="Community Administration API",
    description="Community Administration System API",
    debug=settings.debug,
    version="2.0.0",
    lifespan=lifespan
)

import traceback
from fastapi import Request


@app.middleware("http")
async def log_exceptions(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        print("\n=== UNHANDLED EXCEPTION ===")
        print(f"{request.method} {request.url}")
        traceback.print_exc()
        print("=== END EXCEPTION ===\n")
        raise


# Configure CORS
print("CORS ORIGINS:", settings.cors_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(bodies.router)
app.include_router(offices.router)
app.include_router(persons.router)
app.include_router(terms.router)
app.include_router(letters.router)  # Now uses /api/letters prefix
app.include_router(reports.router)  # Reports/rosters generation
app.include_router(mailing_lists.router)  # Mailing list generation
app.include_router(users.router)  # Local user management


@app.get("/")
async def root():
    """Root endpoint - API health check"""
    return {
        "message": "Community Administration System API",
        "version": "2.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/report-records", response_model=List[dict])
async def get_report_records(db: Session = Depends(get_db)):
    """Get all report records (view data for roster/report generation)"""
    records = db.query(ReportRecord).all()
    return [
        {
            "person_id": r.person_id,
            "first": r.first,
            "last": r.last,
            "email": r.email,
            "phone": r.phone,
            "apt": r.apt,
            "start": r.start.isoformat() if r.start else None,
            "end": r.end.isoformat() if r.end else None,
            "ordinal": r.ordinal,
            "office_id": r.office_id,
            "title": r.title,
            "body_id": r.body_id,
            "name": r.name,
        }
        for r in records
    ]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
