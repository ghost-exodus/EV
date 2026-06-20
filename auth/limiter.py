"""
Rate limiter setup using slowapi.
Defines a key function based on JWT subject (username) falling back to IP.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request


def get_jwt_subject(request: Request) -> str:
    """
    Key function for slowapi: extracts the JWT subject (username) if present,
    otherwise falls back to the client IP address.
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            # Import dynamically to avoid circular references
            from auth.jwt_handler import decode_token
            payload = decode_token(token)
            username = payload.get("sub")
            if username:
                return username
        except Exception:
            pass
    return get_remote_address(request)


# Default limit from env, falling back to 100 requests per minute
import os
rate_limit_rule = os.getenv("RATE_LIMIT_RULE", "100/minute")
limiter = Limiter(key_func=get_jwt_subject, default_limits=[rate_limit_rule])
