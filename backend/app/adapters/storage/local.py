"""Local filesystem storage adapter."""
import os
from pathlib import Path
from typing import Optional

import aiofiles


class LocalStorageService:
    """Local filesystem implementation of StorageService.

    Stores files in a local directory with proper organization.
    """

    def __init__(self, base_path: str):
        """Initialize local storage service.

        Args:
            base_path: Base directory for file storage
        """
        # Convert to absolute path to ensure consistent path resolution
        # regardless of current working directory
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save(self, content: bytes, relative_path: str) -> str:
        """Save file content to local filesystem.

        Args:
            content: File content as bytes
            relative_path: Relative path within storage (e.g., "uploads/file.pdf")

        Returns:
            Full storage path

        Raises:
            IOError: If save operation fails
        """
        full_path = self.base_path / relative_path

        # Create parent directories if they don't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with aiofiles.open(full_path, 'wb') as f:
                await f.write(content)
            return str(full_path)
        except Exception as e:
            raise IOError(f"Failed to save file to {full_path}: {e}") from e

    async def get(self, path: str) -> bytes:
        """Retrieve file content from local filesystem.

        Args:
            path: Storage path (can be relative or absolute)

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If read operation fails
        """
        file_path = Path(path)

        # Handle different path formats:
        # 1. Absolute paths (new format): use as-is
        # 2. Relative paths without base_path prefix: prepend base_path
        # 3. Relative paths with base_path prefix (legacy): resolve from cwd
        if not file_path.is_absolute():
            # Try prepending base_path first (for paths like "projects/xxx/file.pdf")
            candidate = self.base_path / file_path
            if candidate.exists():
                file_path = candidate
            else:
                # Fall back to resolving from current directory (for legacy paths)
                file_path = file_path.resolve()

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            async with aiofiles.open(file_path, 'rb') as f:
                return await f.read()
        except Exception as e:
            raise IOError(f"Failed to read file from {file_path}: {e}") from e

    async def delete(self, path: str) -> None:
        """Delete file from local filesystem.

        Args:
            path: Storage path (can be relative or absolute)

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If delete operation fails
        """
        file_path = Path(path)

        # Handle different path formats (same logic as get method)
        if not file_path.is_absolute():
            candidate = self.base_path / file_path
            if candidate.exists():
                file_path = candidate
            else:
                file_path = file_path.resolve()

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            file_path.unlink()
        except Exception as e:
            raise IOError(f"Failed to delete file {file_path}: {e}") from e

    async def exists(self, path: str) -> bool:
        """Check if file exists in local filesystem.

        Args:
            path: Storage path (can be relative or absolute)

        Returns:
            True if file exists, False otherwise
        """
        file_path = Path(path)

        # Handle different path formats (same logic as get method)
        if not file_path.is_absolute():
            candidate = self.base_path / file_path
            if candidate.exists():
                file_path = candidate
            else:
                file_path = file_path.resolve()

        return file_path.exists() and file_path.is_file()
