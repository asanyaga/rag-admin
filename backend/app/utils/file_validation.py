"""File validation utilities for document uploads."""
import hashlib
import mimetypes
from pathlib import Path
from typing import BinaryIO

import magic


class FileValidationError(Exception):
    """Raised when file validation fails."""
    pass


def validate_file_size(file_size: int, max_size_mb: int = 25) -> None:
    """Validate file size is within limits.

    Args:
        file_size: File size in bytes
        max_size_mb: Maximum allowed size in megabytes

    Raises:
        FileValidationError: If file size exceeds limit
    """
    max_size_bytes = max_size_mb * 1024 * 1024

    if file_size > max_size_bytes:
        raise FileValidationError(
            f"File size {file_size / 1024 / 1024:.2f}MB exceeds maximum allowed size of {max_size_mb}MB"
        )

    if file_size == 0:
        raise FileValidationError("File is empty")


def validate_mime_type(file_content: bytes, filename: str, allowed_types: list[str]) -> str:
    """Validate and detect file MIME type.

    Uses python-magic for accurate MIME type detection based on file content,
    with fallback to extension-based detection.

    Args:
        file_content: File content as bytes (at least first few KB)
        filename: Original filename
        allowed_types: List of allowed MIME types (e.g., ["application/pdf"])

    Returns:
        Detected MIME type

    Raises:
        FileValidationError: If MIME type is not allowed or cannot be detected
    """
    # Try to detect MIME type from content using python-magic
    try:
        mime = magic.Magic(mime=True)
        detected_mime = mime.from_buffer(file_content[:2048])  # Read first 2KB
    except Exception:
        # Fallback to extension-based detection
        detected_mime, _ = mimetypes.guess_type(filename)
        if not detected_mime:
            raise FileValidationError(f"Could not determine MIME type for file: {filename}")

    # Validate against allowed types
    if detected_mime not in allowed_types:
        raise FileValidationError(
            f"File type '{detected_mime}' is not allowed. Allowed types: {', '.join(allowed_types)}"
        )

    return detected_mime


def compute_checksum(content: bytes) -> str:
    """Compute SHA-256 checksum of file content.

    Args:
        content: File content as bytes

    Returns:
        Hexadecimal SHA-256 checksum
    """
    return hashlib.sha256(content).hexdigest()


async def compute_checksum_from_file(file_path: str) -> str:
    """Compute SHA-256 checksum from file path.

    Args:
        file_path: Path to the file

    Returns:
        Hexadecimal SHA-256 checksum

    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read
    """
    import aiofiles

    sha256 = hashlib.sha256()

    try:
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except Exception as e:
        raise IOError(f"Failed to compute checksum for {file_path}: {e}") from e


def get_file_extension(filename: str) -> str:
    """Extract file extension from filename.

    Args:
        filename: Original filename

    Returns:
        File extension including the dot (e.g., ".pdf"), or empty string if no extension
    """
    return Path(filename).suffix.lower()
