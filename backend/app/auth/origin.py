"""Exact browser-origin enforcement. GET generation remains blocked on Step 3C-2.

Restoration blocker: this guard deliberately does not protect file-generating
GET routes (including optional roster publication); convert those in Step 3C-2.
"""

import ipaddress
import re
from urllib.parse import urlsplit

from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse


def valid_origin(value: str) -> bool:
    """Accept only a serialized HTTP(S) origin, never a URL with extra parts."""
    if not isinstance(value, str) or not value.isascii():
        return False
    if re.search(r"[\s\\?#@]", value):
        return False
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or parsed.path or not parsed.hostname:
            return False
        host = parsed.hostname
        if ":" in host:
            ipaddress.IPv6Address(host)
            authority = f"[{host}]"
        else:
            if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*", host):
                return False
            authority = host
        port = parsed.port
        if port is not None:
            if not 1 <= port <= 65535:
                return False
            authority += f":{port}"
        return value == f"{parsed.scheme}://{authority}"
    except ValueError:
        return False


class TrustedOriginMiddleware:
    def __init__(self, app, allowed_origins):
        self.app = app
        self.allowed_origins = frozenset(allowed_origins)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] in {"POST", "PUT", "PATCH", "DELETE"}:
            origins = [value.decode("latin-1") for key, value in scope["headers"] if key.lower() == b"origin"]
            if len(origins) != 1 or not valid_origin(origins[0]) or origins[0] not in self.allowed_origins:
                await JSONResponse({"detail": "Trusted Origin required"}, status_code=403)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def configure_origin_protection(app, allowed_origins):
    """Use one immutable allowlist for both middleware layers."""
    origins = tuple(allowed_origins)
    app.add_middleware(TrustedOriginMiddleware, allowed_origins=origins)
    # CORS wraps the guard so trusted clients can read authorization failures.
    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )
