from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings
from app.db.base import get_db
from app.db import models  # Register models
from app.security.auth import ClerkUser, get_current_user
from app.api.routers import bodies, persons, reports, offices, terms, auth, users, letters

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register API routers
app.include_router(bodies.router, prefix="/api/v1")
app.include_router(persons.router, prefix="/api/v1")
app.include_router(offices.router, prefix="/api/v1")
app.include_router(terms.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"]) 
app.include_router(users.router, prefix="/api/v1/users", tags=["User Management"]) 
app.include_router(letters.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "message": "Community Admin API",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Database connectivity check
@app.get("/api/v1/db-check")
def database_check(db: Session = Depends(get_db)):
    from app.db.models import Body, Office, Person, Term
    try:
        body_count = db.query(Body).count()
        office_count = db.query(Office).count()
        person_count = db.query(Person).count()
        term_count = db.query(Term).count()
        return {
            "status": "connected",
            "database": "sqlite3",
            "bodies": body_count,
            "offices": office_count,
            "persons": person_count,
            "terms": term_count
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# Protected endpoints using Clerk JWT authentication
@app.get(f"{settings.API_V1_PREFIX}/me")
async def get_me(current_user: ClerkUser = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "email_verified": current_user.email_verified,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "full_name": current_user.full_name,
    }


@app.get(f"{settings.API_V1_PREFIX}/protected")
async def protected(current_user: ClerkUser = Depends(get_current_user)):
    name = (
        current_user.full_name
        or current_user.first_name
        or current_user.last_name
        or current_user.user_id
    )
    return {"message": f"Hello, {name}! You have accessed a protected endpoint."}


# Test endpoint for report_record view
@app.get("/api/v1/test-report")
def test_report_view(db: Session = Depends(get_db)):
    """Test the report_record view"""
    try:
        result = db.execute(text("SELECT * FROM report_record LIMIT 10"))
        rows = [dict(row._mapping) for row in result]
        return {
            "status": "success",
            "count": len(rows),
            "sample": rows
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
