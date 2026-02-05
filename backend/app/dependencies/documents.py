"""Dependencies for document-related operations."""
from functools import lru_cache

from app.adapters.llamaindex import LlamaIndexExtractor
from app.adapters.storage import LocalStorageService
from app.config import settings
from app.ports import DocumentExtractor, StorageService


@lru_cache()
def get_storage_service() -> StorageService:
    """Get storage service instance (singleton).

    Returns:
        StorageService implementation (LocalStorageService)
    """
    return LocalStorageService(base_path=settings.DOCUMENT_STORAGE_PATH)


@lru_cache()
def get_document_extractor() -> DocumentExtractor:
    """Get document extractor instance (singleton).

    Returns:
        DocumentExtractor implementation (LlamaIndexExtractor)
    """
    return LlamaIndexExtractor()
