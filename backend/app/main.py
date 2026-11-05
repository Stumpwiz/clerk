# app/main.py - FastAPI application entry point

from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI
from app.auth.origin import configure_origin_protection

from app.config import settings
from app.routers import avatars

# Import routers
from app.routers import auth, bodies, offices, persons, terms, letters, reports, users, mailing_lists, help


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
configure_origin_protection(app, settings.cors_origins)

# Include routers
app.include_router(auth.router)
app.include_router(avatars.router)
app.include_router(bodies.router)
app.include_router(offices.router)
app.include_router(persons.router)
app.include_router(terms.router)
app.include_router(letters.router)  # Now uses /api/letters prefix
app.include_router(reports.router)  # Reports/rosters generation
app.include_router(mailing_lists.router)  # Mailing list generation
app.include_router(users.router)  # Local user management
app.include_router(help.router)  # Administrative Assistant help guide


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
