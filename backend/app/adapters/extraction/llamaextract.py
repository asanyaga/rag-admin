"""LlamaExtract adapter — CDM-based DataExtractor port implementation."""
from typing import Any
from uuid import UUID

from llama_cloud import AsyncLlamaCloud

from app.ports.data_extraction import DataExtractor, ExtractionOutput
from app.ports.storage import StorageService
from app.repositories.source_document_repository import SourceDocumentRepository


class LlamaExtractAdapter(DataExtractor):
    """Structured extraction via LlamaCloud using a CDM ParsedDocument as input."""

    def __init__(
        self,
        api_key: str | None,
        source_document_repo: SourceDocumentRepository,
        storage_service: StorageService,
    ):
        self._api_key = api_key
        self._client: AsyncLlamaCloud | None = None
        self._source_doc_repo = source_document_repo
        self._storage_service = storage_service

    def _get_client(self) -> AsyncLlamaCloud:
        """Lazily create the HTTP client so construction works without credentials."""
        if self._client is None:
            self._client = AsyncLlamaCloud(api_key=self._api_key)
        return self._client

    @property
    def extractor_type(self) -> str:
        return "llamaextract"

    @property
    def display_name(self) -> str:
        return "LlamaExtract"

    async def _get_file_bytes(self, source_document_id: str) -> bytes:
        source_doc = await self._source_doc_repo.get(UUID(source_document_id))
        if not source_doc:
            raise ValueError(f"SourceDocument {source_document_id} not found")
        return await self._storage_service.get(source_doc.storage_uri)

    async def extract(
        self,
        parsed_document: Any,
        schema: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> ExtractionOutput:
        raise NotImplementedError("extract() — see Task 3 of the implementation plan")
