"""Encryption utilities for sensitive data storage.

Uses Fernet symmetric encryption for encrypting API keys and other secrets.
Fernet guarantees that data encrypted using it cannot be further manipulated
or read without the key.
"""
import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class EncryptionError(Exception):
    """Raised when encryption or decryption fails."""
    pass


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Get or create a Fernet instance with the configured encryption key.

    The key is cached to avoid repeated initialization overhead.
    """
    key = settings.ENCRYPTION_KEY

    # If the key looks like a raw string (not base64), derive a proper Fernet key
    # This allows users to use simpler secret strings
    try:
        # Check if it's already a valid Fernet key (32-byte base64)
        Fernet(key.encode() if isinstance(key, str) else key)
        fernet_key = key.encode() if isinstance(key, str) else key
    except (ValueError, InvalidToken):
        # Derive a proper Fernet key from the provided string
        # Use SHA256 to get 32 bytes, then base64 encode
        derived = hashlib.sha256(key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(derived)

    return Fernet(fernet_key)


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return the encrypted value as a base64 string.

    Args:
        plaintext: The string to encrypt

    Returns:
        Base64-encoded encrypted string

    Raises:
        EncryptionError: If encryption fails
    """
    if not plaintext:
        raise EncryptionError("Cannot encrypt empty string")

    try:
        fernet = _get_fernet()
        encrypted = fernet.encrypt(plaintext.encode())
        return encrypted.decode()
    except Exception as e:
        raise EncryptionError(f"Encryption failed: {e}") from e


def decrypt(ciphertext: str) -> str:
    """Decrypt a base64-encoded encrypted string.

    Args:
        ciphertext: The encrypted string to decrypt

    Returns:
        The original plaintext string

    Raises:
        EncryptionError: If decryption fails (invalid key, corrupted data, etc.)
    """
    if not ciphertext:
        raise EncryptionError("Cannot decrypt empty string")

    try:
        fernet = _get_fernet()
        decrypted = fernet.decrypt(ciphertext.encode())
        return decrypted.decode()
    except InvalidToken:
        raise EncryptionError("Decryption failed: invalid token or wrong key")
    except Exception as e:
        raise EncryptionError(f"Decryption failed: {e}") from e


def mask_key(api_key: str, visible_chars: int = 4) -> str:
    """Mask an API key for display purposes, showing only the last few characters.

    Args:
        api_key: The API key to mask
        visible_chars: Number of characters to show at the end

    Returns:
        Masked string like "sk-****abcd"
    """
    if not api_key:
        return ""

    if len(api_key) <= visible_chars:
        return "*" * len(api_key)

    # Show prefix if it looks like a standard API key format (e.g., "sk-")
    prefix = ""
    if "-" in api_key[:5]:
        prefix_end = api_key.index("-") + 1
        prefix = api_key[:prefix_end]
        remaining = api_key[prefix_end:]
    else:
        remaining = api_key

    visible_part = remaining[-visible_chars:] if len(remaining) > visible_chars else remaining
    hidden_length = len(remaining) - len(visible_part)

    return f"{prefix}{'*' * hidden_length}{visible_part}"
