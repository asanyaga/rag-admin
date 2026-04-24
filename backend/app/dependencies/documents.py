"""Dependencies for document-related operations."""
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llamaindex import LlamaIndexExtractor
from app.adapters.storage import LocalStorageService
from app.config import settings
from app.ports import DocumentExtractor, StorageService
from app.repositories.parse_run_repository import ParseRunRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.services.parsing.parsing_service import ParsingService


@lru_cache()
def get_storage_service() -> StorageService:
    """Get storage service instance (singleton)."""
    return LocalStorageService(base_path=settings.DOCUMENT_STORAGE_PATH)


@lru_cache()
def get_document_extractor() -> DocumentExtractor:
    """Get document extractor instance (singleton)."""
    return LlamaIndexExtractor()


def get_llamaparse_client() -> Any:
    """Create an AsyncLlamaCloud client from settings.LLAMA_CLOUD_KEY."""
    from llama_cloud import AsyncLlamaCloud
    if settings.LLAMA_CLOUD_KEY:
        return AsyncLlamaCloud(api_key=settings.LLAMA_CLOUD_KEY)
    return AsyncLlamaCloud()


def get_parsing_service(db: AsyncSession) -> ParsingService:
    """Create a per-request ParsingService wired to the current db session."""
    return ParsingService(
        source_doc_repo=SourceDocumentRepository(db),
        parse_run_repo=ParseRunRepository(db),
        parsed_doc_repo=ParsedDocumentRepository(db),
        storage=get_storage_service(),
        llamaparse_client=get_llamaparse_client(),
    )
