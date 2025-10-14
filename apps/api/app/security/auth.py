from __future__ import annotations

from typing import Any, Dict, Optional

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.db.models import User




class ClerkUser(BaseModel):
    user_id: str
    email: Optional[str] = None
    email_verified: Optional[bool] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    claims: Dict[str, Any]


def _extract_issuer(token: str) -> str:
    try:
        unverified_payload = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,
                "verify_iss": False,
            },
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    issuer = unverified_payload.get("iss")
    if not issuer or not isinstance(issuer, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing issuer",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return issuer.rstrip("/")


def _claims_to_user(payload: Dict[str, Any]) -> ClerkUser:
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Email and verification flags from common Clerk/JWT claims
    email = (
        payload.get("email")
        or payload.get("primary_email_address")
        or payload.get("email_address")
    )

    email_verified: Optional[bool] = None
    if "email_verified" in payload:
        email_verified = bool(payload.get("email_verified"))
    else:
        # Some tokens may include an array of email_addresses with verification status
        emails = payload.get("email_addresses")
        if isinstance(emails, list) and emails:
            # try to find primary
            primary = next((e for e in emails if isinstance(e, dict) and e.get("id") == payload.get("primary_email_address_id")), None)
            candidate = primary or emails[0]
            if isinstance(candidate, dict):
                email = email or candidate.get("email_address")
                ver = candidate.get("verification", {})
                if isinstance(ver, dict):
                    email_verified = ver.get("status") == "verified"

    first_name = payload.get("given_name") or payload.get("first_name")
    last_name = payload.get("family_name") or payload.get("last_name")

    full_name = payload.get("name")
    if not full_name:
        if first_name and last_name:
            full_name = f"{first_name} {last_name}"
        else:
            full_name = first_name or last_name

    return ClerkUser(
        user_id=str(sub),
        email=email,
        email_verified=email_verified,
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
        claims=payload,
    )


def verify_token(token: str) -> ClerkUser:
    """
    Verify a Clerk JWT using PyJWT and JWKS and return a ClerkUser.

    Steps:
    - Extract issuer (iss) claim without verifying the signature first.
    - Construct JWKS URL as {issuer}/.well-known/jwks.json
    - Fetch signing key via PyJWKClient and verify using RS256
    - Validate issuer and expiration
    - Return mapped ClerkUser
    """
    issuer = _extract_issuer(token)
    jwks_url = f"{issuer}/.well-known/jwks.json"

    try:
        jwk_client = PyJWKClient(jwks_url)
        signing_key = jwk_client.get_signing_key_from_jwt(token)

        payload = jwt.decode(
            token,
            key=signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False},
        )
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\", error_description=\"The access token expired\""},
        )
    except jwt.InvalidIssuerError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token issuer",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _claims_to_user(payload)


# Simple HTTPBearer without customization
http_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer)
) -> ClerkUser:
    """
    Verify Clerk JWT token and extract user information.
    Depends on HTTPBearer to extract credentials from Authorization header.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    return verify_token(token)



class AuthorizedUser(BaseModel):
    """User with both Clerk authentication and database authorization"""
    clerk_user_id: str
    email: str
    username: str
    role: str  # "admin" or "user"
    clerk_data: ClerkUser  # Full Clerk JWT claims


async def get_authorized_user(
    clerk_user: ClerkUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> AuthorizedUser:
    """
    Verify that the authenticated Clerk user is authorized in our database.
    """
    # Get email from Clerk JWT claims
    email = clerk_user.email


    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not found in JWT claims"
        )
    
    # Check if user exists in our users table
    db_user = db.query(User).filter(User.email == email).first()
    
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Access denied. Your email is not authorized to use this application. "
                "Please contact an administrator to request access."
            ),
        )
    
    # Return authorized user with database role
    return AuthorizedUser(
        clerk_user_id=clerk_user.user_id,
        email=db_user.email,
        username=db_user.username,
        role=db_user.role,
        clerk_data=clerk_user,
    )


def require_admin(current_user: AuthorizedUser = Depends(get_authorized_user)) -> AuthorizedUser:
    """
    Dependency that requires the current user to be an admin.
    
    Raises:
        HTTPException 403: If user is not an admin
    
    Returns:
        AuthorizedUser with admin role
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required"
        )
    return current_user
