"""Storage service port interface."""
from typing import Protocol


class StorageService(Protocol):
    """Port interface for file storage operations.

    Implementations can use local filesystem, S3, GCS, etc.
    """

    async def save(self, content: bytes, relative_path: str) -> str:
        """Save file content and return the storage path.

        Args:
            content: File content as bytes
            relative_path: Relative path within storage (e.g., "uploads/file.pdf")

        Returns:
            Full storage path or identifier

        Raises:
            IOError: If save operation fails
        """
        ...

    async def get(self, path: str) -> bytes:
        """Retrieve file content by path.

        Args:
            path: Storage path or identifier

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If read operation fails
        """
        ...

    async def delete(self, path: str) -> None:
        """Delete file by path.

        Args:
            path: Storage path or identifier

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If delete operation fails
        """
        ...

    async def exists(self, path: str) -> bool:
        """Check if file exists.

        Args:
            path: Storage path or identifier

        Returns:
            True if file exists, False otherwise
        """
        ...
