import time
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from jose import jwt

from app.config import settings
from app.utils.jwt import create_access_token, create_refresh_token, decode_access_token, hash_refresh_token


def test_create_access_token():
    user_id = uuid4()
    email = "test@example.com"

    token = create_access_token(user_id, email)

    assert isinstance(token, str)
    assert len(token) > 0

    # Decode manually to verify contents
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert payload["sub"] == str(user_id)
    assert payload["email"] == email
    assert "exp" in payload
    assert "iat" in payload


def test_decode_access_token_valid():
    user_id = uuid4()
    email = "test@example.com"

    token = create_access_token(user_id, email)
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == str(user_id)
    assert payload["email"] == email


def test_decode_access_token_invalid():
    invalid_token = "invalid.token.here"

    payload = decode_access_token(invalid_token)

    assert payload is None


def test_decode_access_token_expired():
    user_id = uuid4()
    email = "test@example.com"

    # Create token that expires immediately
    expire = datetime.utcnow() - timedelta(seconds=1)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    expired_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    # Wait a moment to ensure it's expired
    time.sleep(0.1)

    decoded_payload = decode_access_token(expired_token)

    assert decoded_payload is None


def test_create_refresh_token():
    token1 = create_refresh_token()
    token2 = create_refresh_token()

    assert isinstance(token1, str)
    assert isinstance(token2, str)
    assert len(token1) > 30
    assert len(token2) > 30
    assert token1 != token2  # Should be unique


def test_hash_refresh_token():
    token = "test-refresh-token-12345"
    hashed = hash_refresh_token(token)

    assert isinstance(hashed, str)
    assert len(hashed) == 64  # SHA-256 produces 64 hex characters
    assert hashed != token
    assert hashed.isalnum()  # Should only contain hex characters


def test_hash_refresh_token_consistent():
    """Same token should produce the same hash."""
    token = "test-refresh-token-12345"
    hash1 = hash_refresh_token(token)
    hash2 = hash_refresh_token(token)

    assert hash1 == hash2


def test_hash_refresh_token_different():
    """Different tokens should produce different hashes."""
    token1 = "test-refresh-token-1"
    token2 = "test-refresh-token-2"
    hash1 = hash_refresh_token(token1)
    hash2 = hash_refresh_token(token2)

    assert hash1 != hash2
