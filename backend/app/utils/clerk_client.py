# app/utils/clerk_client.py - Clerk API client for user management

import requests
from typing import List, Dict, Optional
from app.config import settings


class ClerkClient:
    """Client for interacting with Clerk's API"""

    BASE_URL = "https://api.clerk.com/v1"

    def __init__(self):
        self.secret_key = settings.clerk_secret_key
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    def list_users(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        List all users from Clerk

        Args:
            limit: Maximum number of users to return
            offset: Number of users to skip

        Returns:
            List of user dictionaries
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/users",
                headers=self.headers,
                params={"limit": limit, "offset": offset}
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch users from Clerk: {str(e)}")

    def get_user(self, user_id: str) -> Dict:
        """
        Get a specific user by ID

        Args:
            user_id: Clerk user ID

        Returns:
            User dictionary
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/users/{user_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch user from Clerk: {str(e)}")

    def create_invitation(self, email_address: str, redirect_url: Optional[str] = None) -> Dict:
        """
        Send an invitation email to a new user

        Args:
            email_address: Email address to send invitation to
            redirect_url: Optional URL to redirect to after sign-up

        Returns:
            Invitation dictionary
        """
        try:
            payload = {
                "email_address": email_address,
                "public_metadata": {},
                "notify": True  # Clerk requires this to send the invitation email
            }

            if redirect_url:
                payload["redirect_url"] = redirect_url

            response = requests.post(
                f"{self.BASE_URL}/invitations",
                headers=self.headers,
                json=payload
            )

            # If there's an error, try to get the detailed error message
            if not response.ok:
                error_detail = "Unknown error"
                try:
                    error_data = response.json()
                    # Clerk API returns errors in various formats
                    if "errors" in error_data:
                        error_detail = str(error_data["errors"])
                    elif "message" in error_data:
                        error_detail = error_data["message"]
                    elif "error" in error_data:
                        error_detail = error_data["error"]
                    else:
                        error_detail = str(error_data)
                except Exception:
                    error_detail = response.text or f"HTTP {response.status_code}"

                raise Exception(f"Clerk API error ({response.status_code}): {error_detail}")

            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to create invitation: {str(e)}")

    def revoke_invitation(self, invitation_id: str) -> Dict:
        """
        Revoke a pending invitation

        Args:
            invitation_id: Clerk invitation ID

        Returns:
            Revoked invitation dictionary
        """
        try:
            response = requests.post(
                f"{self.BASE_URL}/invitations/{invitation_id}/revoke",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to revoke invitation: {str(e)}")

    def list_invitations(self, status: Optional[str] = None) -> List[Dict]:
        """
        List all invitations

        Args:
            status: Optional status filter (pending, accepted, revoked)

        Returns:
            List of invitation dictionaries
        """
        try:
            params = {}
            if status:
                params["status"] = status

            response = requests.get(
                f"{self.BASE_URL}/invitations",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch invitations: {str(e)}")


# Singleton instance
clerk_client = ClerkClient()
