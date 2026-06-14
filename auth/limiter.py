"""
Rate limiter setup using slowapi.
Defines a key function based on JWT subject (username) falling back to IP.

The decoded JWT payload is cached in request.state.jwt_payload so that
downstream middleware (logging) and dependencies (verify_jwt) can reuse it
instead of redundantly decoding the token (3 RSA verifications → 1).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request


def get_jwt_subject(request: Request) -> str:
    """
    Key function for slowapi: extracts the JWT subject (username) if present,
    otherwise falls back to the client IP address.

    Side effect: caches decoded payload in request.state.jwt_payload.
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            # Import dynamically to avoid circular references
            from auth.jwt_handler import decode_token
            payload = decode_token(token)
            # Cache for reuse by logging middleware and verify_jwt dependency
            request.state.jwt_payload = payload
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

