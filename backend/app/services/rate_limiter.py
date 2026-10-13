"""Slowapi rate limiter configuration with per-user and per-IP key functions."""

import logging
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.services.auth import decode_access_token

logger = logging.getLogger(__name__)


def get_user_rate_limit_key(request: Request) -> str:
    """Identify the client by user ID (from JWT) or fallback to remote IP address."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        payload = decode_access_token(token)
        if payload and "sub" in payload:
            return f"user:{payload['sub']}"

    # Fallback to client remote IP address
    return get_remote_address(request) or "unknown_client"


# Global limiter instance
limiter = Limiter(key_func=get_user_rate_limit_key)
