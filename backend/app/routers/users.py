# app/routers/users.py - User management via Clerk API

from fastapi import APIRouter, HTTPException
from typing import List, Dict
from pydantic import BaseModel, EmailStr
import hashlib

from app.utils.clerk_client import clerk_client

router = APIRouter(prefix="/api/users", tags=["users"])


def get_gravatar_url(email: str, size: int = 200) -> str:
    """
    Generate gravatar URL from email address

    Args:
        email: User's email address
        size: Image size in pixels (default 200)

    Returns:
        Gravatar URL
    """
    # Gravatar requires lowercase, trimmed email
    email_hash = hashlib.md5(email.lower().strip().encode('utf-8')).hexdigest()
    return f"https://www.gravatar.com/avatar/{email_hash}?s={size}&d=mp"


class InvitationRequest(BaseModel):
    email: EmailStr
    redirect_url: str = None


class InvitationResponse(BaseModel):
    success: bool
    message: str
    invitation: Dict = None


@router.get("/list", response_model=List[Dict])
async def list_users():
    """
    Get all users from Clerk

    Returns a list of users with their basic information
    """
    try:
        users = clerk_client.list_users(limit=500)

        # Transform to a simpler format for the frontend
        simplified_users = []
        for user in users:
            email = user.get("email_addresses", [{}])[0].get("email_address", "")

            simplified_users.append({
                "id": user.get("id"),
                "email": email,
                "first_name": user.get("first_name", ""),
                "last_name": user.get("last_name", ""),
                "created_at": user.get("created_at"),
                "updated_at": user.get("updated_at"),
                "last_sign_in_at": user.get("last_sign_in_at"),
                "profile_image_url": get_gravatar_url(email) if email else "",
            })

        return simplified_users

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/invite", response_model=InvitationResponse)
async def invite_user(request: InvitationRequest):
    """
    Send an invitation email to a new user via Clerk

    Args:
        request: Contains email address and optional redirect URL

    Returns:
        Success status and invitation details
    """
    try:
        invitation = clerk_client.create_invitation(
            email_address=request.email,
            redirect_url=request.redirect_url
        )

        return InvitationResponse(
            success=True,
            message=f"Invitation sent successfully to {request.email}",
            invitation=invitation
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send invitation: {str(e)}"
        )


@router.get("/invitations", response_model=List[Dict])
async def list_invitations(status: str = None):
    """
    Get all pending invitations from Clerk

    Args:
        status: Optional filter by status (pending, accepted, revoked)

    Returns:
        List of invitations
    """
    try:
        invitations = clerk_client.list_invitations(status=status)

        # Transform to simpler format
        simplified_invitations = []
        for inv in invitations:
            simplified_invitations.append({
                "id": inv.get("id"),
                "email": inv.get("email_address"),
                "status": inv.get("status"),
                "created_at": inv.get("created_at"),
                "updated_at": inv.get("updated_at"),
            })

        return simplified_invitations

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/invitations/{invitation_id}/revoke")
async def revoke_invitation(invitation_id: str):
    """
    Revoke a pending invitation

    Args:
        invitation_id: Clerk invitation ID

    Returns:
        Success status
    """
    try:
        clerk_client.revoke_invitation(invitation_id)
        return {"success": True, "message": "Invitation revoked successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to revoke invitation: {str(e)}"
        )
