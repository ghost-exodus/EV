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


import os

_previous_public_keys = []


def load_previous_public_keys() -> list[str]:
    """Scan previous_keys directory and return a list of PEM public keys."""
    global _previous_public_keys
    keys = []
    if os.path.exists("previous_keys"):
        try:
            for filename in os.listdir("previous_keys"):
                if filename.endswith(".pem"):
                    with open(os.path.join("previous_keys", filename), "r") as f:
                        keys.append(f.read())
        except Exception:
            pass
    _previous_public_keys = keys
    return _previous_public_keys


def decode_token(token: str) -> dict:
    """
    Verify and decode a JWT token using the current RS256 public key,
    falling back to historical public keys in case of recent key rotation.
    Raises HTTPException 401 if invalid or expired.
    """
    global _public_key, _previous_public_keys
    if _public_key is None:
        _public_key = get_public_key()
        load_previous_public_keys()

    # 1. Try decoding with the current public key
    try:
        payload = jwt.decode(token, _public_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        pass

    # 2. Try decoding with each previous public key
    for pub_key in _previous_public_keys:
        try:
            payload = jwt.decode(token, pub_key, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            continue

    # 3. If it fails, reload from disk in case a rotation happened recently
    try:
        # Reset local caches
        _public_key = None
        current_pub = get_public_key()
        prev_keys = load_previous_public_keys()
        
        # Try current again
        try:
            return jwt.decode(token, current_pub, algorithms=[ALGORITHM])
        except JWTError:
            pass

        # Try previous again
        for pub_key in prev_keys:
            try:
                return jwt.decode(token, pub_key, algorithms=[ALGORITHM])
            except JWTError:
                continue
    except Exception:
        pass

    # 4. If all fail, raise unauthorized exception
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
