"""LlamaExtract adapter — CDM-based DataExtractor port implementation."""
import time
from typing import Any
from uuid import UUID

from llama_cloud import AsyncLlamaCloud

from app.ports.data_extraction import DataExtractor, ExtractionError, ExtractionOutput
from app.ports.storage import StorageService
from app.repositories.source_document_repository import SourceDocumentRepository

_SUPPORTED_MIME_TYPES = {"application/pdf"}
_DEFAULT_FILENAME_BY_MIME = {
    "application/pdf": "document.pdf",
}


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

    async def _get_file_bytes(self, source_document_id: str) -> tuple[bytes, str]:
        """Return (file_bytes, mime_type). Raises ExtractionError for unsupported formats."""
        if self._source_doc_repo is None or self._storage_service is None:
            raise RuntimeError(
                "LlamaExtractAdapter requires source_document_repo and storage_service; "
                "pass them via get_extractor(..., dependencies={...})"
            )
        source_doc = await self._source_doc_repo.get(UUID(source_document_id))
        if not source_doc:
            raise ValueError(f"SourceDocument {source_document_id} not found")
        mime_type = source_doc.mime_type or "application/octet-stream"
        if source_doc.mime_type and source_doc.mime_type not in _SUPPORTED_MIME_TYPES:
            raise ExtractionError(
                f"LlamaExtract only supports PDF files. "
                f"This document is '{source_doc.mime_type}'. "
                f"Use a text-based extractor (e.g. Ollama) for non-PDF documents."
            )
        file_bytes = await self._storage_service.get(source_doc.storage_uri)
        return file_bytes, mime_type

    async def extract(
        self,
        parsed_document: Any,
        schema: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> ExtractionOutput:
        config = config or {}

        file_bytes, mime_type = await self._get_file_bytes(parsed_document.source_document_id)
        filename = _DEFAULT_FILENAME_BY_MIME.get(mime_type, "document.pdf")
        client = self._get_client()
        file_obj = await client.files.create(
            file=(filename, file_bytes, mime_type),
            purpose="extract",
        )

        extraction_config: dict[str, Any] = {
            "extraction_mode": config.get("extraction_mode", "MULTIMODAL"),
            "extraction_target": config.get("extraction_target", "PER_DOC"),
        }
        if config.get("cite_sources") is not None:
            extraction_config["cite_sources"] = config["cite_sources"]
        if config.get("use_reasoning") is not None:
            extraction_config["use_reasoning"] = config["use_reasoning"]
        if config.get("confidence_scores") is not None:
            extraction_config["confidence_scores"] = config["confidence_scores"]
        if config.get("page_range") is not None:
            extraction_config["page_range"] = config["page_range"]
        if config.get("system_prompt") is not None:
            extraction_config["prompt_override"] = config["system_prompt"]

        t0 = time.monotonic()
        try:
            result = await client.extraction.extract(
                data_schema=schema,
                file_id=file_obj.id,
                config=extraction_config,
            )
        finally:
            latency_ms = int((time.monotonic() - t0) * 1000)
            await client.files.delete(file_obj.id)

        raw_response = result.model_dump() if hasattr(result, "model_dump") else dict(result)

        return ExtractionOutput(
            structured_data=result.data if result.data is not None else {},
            source_parse_run_id=UUID(parsed_document.parse_run_id),
            citations=None,
            provider_response_raw=raw_response,
            extraction_metadata={
                "latency_ms": latency_ms,
                "file_id": str(file_obj.id),
            },
        )
