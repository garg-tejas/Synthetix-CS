from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = _get_env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 30)
REFRESH_TOKEN_EXPIRE_DAYS = _get_env_int("REFRESH_TOKEN_EXPIRE_DAYS", 7)


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(
    subject: str,
    token_type: str,
    expires_delta: Optional[timedelta],
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode: Dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_access_token(subject: str | int, expires_minutes: Optional[int] = None) -> str:
    """Create a short-lived access token for a user."""
    delta = timedelta(minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(str(subject), token_type="access", expires_delta=delta)


def create_refresh_token(subject: str | int, expires_days: Optional[int] = None) -> str:
    """Create a long-lived refresh token for a user."""
    delta = timedelta(days=expires_days or REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_token(str(subject), token_type="refresh", expires_delta=delta)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode a JWT and return its payload.

    Raises JWTError on invalid or expired tokens.
    """
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def create_token_pair(subject: str | int) -> Dict[str, str]:
    """Convenience helper to create both access and refresh tokens."""
    access = create_access_token(subject)
    refresh = create_refresh_token(subject)
    return {"access_token": access, "refresh_token": refresh}

