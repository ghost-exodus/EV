"""
Auth Router — POST /auth/token for user authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from auth.jwt_handler import create_access_token

router = APIRouter()

# Hardcoded demo users
DEMO_USERS = {
    "admin": {"password": "secret", "role": "fleet_admin"},
    "operator": {"password": "secret", "role": "operator"},
}


@router.post(
    "/token",
    summary="Obtain a JWT access token",
    description="Authenticate with username and password to get a bearer token.",
)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Validate the credentials and return a signed access token.
    """
    user = DEMO_USERS.get(form_data.username)
    if not user or user["password"] != form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create the token
    access_token = create_access_token(
        subject=form_data.username,
        role=user["role"],
        expires_minutes=30,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user["role"],
    }
