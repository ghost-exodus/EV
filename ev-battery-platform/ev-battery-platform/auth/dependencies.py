"""
FastAPI dependencies for JWT authentication and role-based access control (RBAC).
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from auth.jwt_handler import decode_token

# The tokenUrl points to POST /auth/token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def verify_jwt(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Dependency to verify the incoming JWT and extract the user subject and role.
    Raises 401 HTTPException if verification fails.
    """
    payload = decode_token(token)
    username = payload.get("sub")
    role = payload.get("role")

    if not username or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject or role claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"username": username, "role": role}


def require_role(*allowed_roles: str):
    """
    Dependency factory to enforce role-based access control (RBAC).
    Raises 403 HTTPException if the current user's role is not permitted.
    """

    def dependency(current_user: dict = Depends(verify_jwt)):
        role = current_user.get("role")
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient permissions for this operation",
            )
        return current_user

    return dependency
