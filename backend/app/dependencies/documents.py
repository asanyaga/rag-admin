"""Dependencies for document-related operations."""
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llamaindex import LlamaIndexExtractor
from app.adapters.storage import LocalStorageService
from app.cdm.models import ParserKind
from app.config import settings
from app.ports import DocumentExtractor, StorageService
from app.repositories.parse_run_repository import ParseRunRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.services.parsing.parsing_service import ParsingService


@lru_cache()
def get_storage_service() -> StorageService:
    return LocalStorageService(base_path=settings.DOCUMENT_STORAGE_PATH)


@lru_cache()
def get_document_extractor() -> DocumentExtractor:
    return LlamaIndexExtractor()


def get_llamaparse_client() -> Any:
    from llama_cloud import AsyncLlamaCloud
    if settings.LLAMA_CLOUD_KEY:
        return AsyncLlamaCloud(api_key=settings.LLAMA_CLOUD_KEY)
    return None


def get_landingai_client() -> Any:
    from landingai_ade import LandingAIADE
    if settings.VISION_AGENT_API_KEY:
        return LandingAIADE(apikey=settings.VISION_AGENT_API_KEY)
    return None


def get_parsing_service(db: AsyncSession) -> ParsingService:
    return ParsingService(
        source_doc_repo=SourceDocumentRepository(db),
        parse_run_repo=ParseRunRepository(db),
        parsed_doc_repo=ParsedDocumentRepository(db),
        storage=get_storage_service(),
        clients={
            ParserKind.LLAMAPARSE: get_llamaparse_client(),
            ParserKind.LANDING_AI: get_landingai_client(),
        },
    )
