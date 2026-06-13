"""
JWT Token handler for signing and verification using RS256.
Loads public/private keys lazily from the project root.
"""

from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException, status

ALGORITHM = "RS256"

_private_key = None
_public_key = None


def get_private_key() -> str:
    """Load private key from disk lazily."""
    global _private_key
    if _private_key is None:
        try:
            with open("private_key.pem", "r") as f:
                _private_key = f.read()
        except FileNotFoundError:
            raise RuntimeError(
                "Private key not found. Please run 'python scripts/generate_keys.py' first."
            )
    return _private_key


def get_public_key() -> str:
    """Load public key from disk lazily."""
    global _public_key
    if _public_key is None:
        try:
            with open("public_key.pem", "r") as f:
                _public_key = f.read()
        except FileNotFoundError:
            raise RuntimeError(
                "Public key not found. Please run 'python scripts/generate_keys.py' first."
            )
    return _public_key


def create_access_token(subject: str, role: str, expires_minutes: int = 30) -> str:
    """
    Generate a JWT access token signed with RS256 private key.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode = {
        "sub": subject,
        "role": role,
        "exp": expire,
    }
    private_key = get_private_key()
    return jwt.encode(to_encode, private_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Verify and decode a JWT token using the RS256 public key.
    Raises HTTPException 401 if invalid or expired.
    """
    public_key = get_public_key()
    try:
        payload = jwt.decode(token, public_key, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
