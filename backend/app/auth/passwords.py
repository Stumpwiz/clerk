"""Password hashing utilities for local authentication."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

HASH_NAME = "sha256"
ITERATIONS = 390_000
SALT_BYTES = 16
KEY_BYTES = 32
SCHEME = "pbkdf2_sha256"


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(f"{encoded}{padding}")


def hash_password(raw_password: str) -> str:
    if not raw_password:
        raise ValueError("Password must not be empty.")

    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        HASH_NAME,
        raw_password.encode("utf-8"),
        salt,
        ITERATIONS,
        dklen=KEY_BYTES,
    )
    return f"{SCHEME}${ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(raw_password: str, password_hash: str | None) -> bool:
    if not raw_password or not password_hash:
        return False

    try:
        scheme, iterations_text, salt_text, digest_text = password_hash.split("$", 3)
        if scheme != SCHEME:
            return False
        iterations = int(iterations_text)
        salt = _b64decode(salt_text)
        expected_digest = _b64decode(digest_text)
    except (TypeError, ValueError):
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        HASH_NAME,
        raw_password.encode("utf-8"),
        salt,
        iterations,
        dklen=len(expected_digest),
    )
    return hmac.compare_digest(actual_digest, expected_digest)
