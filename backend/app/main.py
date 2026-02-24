# app/main.py - FastAPI application entry point

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from app.config import settings
from app.database import get_db
from app.models import ReportRecord

# Import routers
from app.routers import bodies, offices, persons, terms, letters, reports, users


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    print(f"*** {settings.app_name} started ***")
    print(f"Database: {settings.database_url}")
    print(f"API Docs: http://{settings.api_host}:{settings.api_port}/docs")
    yield
    # Shutdown (if needed in the future)
    print("Shutting down...")


# Create FastAPI application
app = FastAPI(
    title="Clerk API",
    description="Community Administration System API",
    debug=settings.debug,
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(bodies.router)
app.include_router(offices.router)
app.include_router(persons.router)
app.include_router(terms.router)
app.include_router(letters.router)  # Now uses /api/letters prefix
app.include_router(reports.router)  # Reports/rosters generation
app.include_router(users.router)  # User management via Clerk


@app.get("/")
async def root():
    """Root endpoint - API health check"""
    return {
        "message": "Clerk - Community Administration System API",
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
