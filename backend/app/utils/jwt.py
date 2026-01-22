import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt

from app.config import settings


def create_access_token(user_id: UUID, email: str) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User's UUID
        email: User's email address

    Returns:
        Encoded JWT token
    """
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT token to decode

    Returns:
        Token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def create_refresh_token() -> str:
    """
    Generate a random refresh token.

    Returns:
        Random URL-safe token string
    """
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """
    Hash a refresh token using SHA-256 for database storage.

    Args:
        token: Plain refresh token

    Returns:
        SHA-256 hash of the token
    """
    return hashlib.sha256(token.encode()).hexdigest()
