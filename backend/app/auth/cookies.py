"""Signed HTTP-only cookie helpers for local authentication sessions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import Response

from app.config import settings


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(f"{encoded}{padding}")


def _signature(payload: str) -> str:
    secret = settings.auth_secret_key.encode("utf-8")
    return _b64encode(hmac.new(secret, payload.encode("ascii"), hashlib.sha256).digest())


def create_session_cookie_value(user_id: int, ttl_seconds: int | None = None) -> str:
    ttl = ttl_seconds if ttl_seconds is not None else settings.session_ttl_seconds
    payload: dict[str, Any] = {
        "sub": user_id,
        "exp": int(time.time()) + ttl,
    }
    payload_text = _b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    return f"{payload_text}.{_signature(payload_text)}"


def parse_session_cookie_value(cookie_value: str | None) -> int | None:
    if not cookie_value:
        return None

    try:
        payload_text, signature = cookie_value.split(".", 1)
    except ValueError:
        return None

    expected_signature = _signature(payload_text)
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        payload = json.loads(_b64decode(payload_text))
        user_id = int(payload["sub"])
        expires_at = int(payload["exp"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None

    if expires_at < int(time.time()):
        return None
    return user_id


def set_session_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=create_session_cookie_value(user_id),
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
    )
