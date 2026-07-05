#!/usr/bin/env python3
"""Create a local authentication user.

This is an administrative bootstrap utility for local authentication. It is
intentionally small and interactive; it is not a production user-management UI.
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.auth.passwords import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402


def prompt_required(prompt: str) -> str:
    value = input(prompt).strip()
    if not value:
        raise ValueError(f"{prompt.rstrip(': ')} is required.")
    return value


def prompt_password() -> str:
    password = getpass.getpass("Password: ")
    if not password:
        raise ValueError("Password is required.")

    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise ValueError("Passwords do not match.")

    return password


def main() -> int:
    try:
        email = prompt_required("Email: ").lower()
        display_name = prompt_required("Display name: ")
        password = prompt_password()

        with SessionLocal() as session:
            existing_user = session.scalar(select(User).where(func.lower(User.email) == email))
            if existing_user is not None:
                print(f"User already exists for email address: {email}", file=sys.stderr)
                return 1

            user = User(
                email=email,
                password_hash=hash_password(password),
                display_name=display_name,
                is_active=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            print(f"Created local user {user.email} (id={user.id}).")
            return 0
    except (KeyboardInterrupt, EOFError):
        print("\nUser creation cancelled.", file=sys.stderr)
        return 130
    except ValueError as exc:
        print(f"User creation failed: {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError as exc:
        print(f"Database error while creating user: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
