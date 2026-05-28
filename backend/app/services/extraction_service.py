"""Extraction service — manages extraction schemas, results, and background extraction."""
import dataclasses
import logging
from datetime import datetime, timedelta
from uuid import UUID

from app.cdm import models as cdm_models
from app.models.extraction_result import ExtractionResultStatus
from app.ports.data_extraction import DataExtractor
from app.repositories.document_repository import DocumentRepository
from app.repositories.extraction_schema_repository import ExtractionSchemaRepository
from app.repositories.extraction_result_repository import ExtractionResultRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.schemas.extraction_result import (
    ExtractionSchemaResponse,
    ExtractionResultResponse,
    ExtractionResultListResponse,
    ExtractorInfoResponse,
)
from app.adapters.extraction.registry import get_known_extractors
from app.services.exceptions import NotFoundError, ConflictError

logger = logging.getLogger(__name__)

STALE_TIMEOUT = timedelta(minutes=10)


class ExtractionService:
    """Service for extraction operations."""

    def __init__(
        self,
        schema_repo: ExtractionSchemaRepository,
        result_repo: ExtractionResultRepository,
        parsed_document_repo: ParsedDocumentRepository,
        document_repo: DocumentRepository,
    ):
        self.schema_repo = schema_repo
        self.result_repo = result_repo
        self.parsed_document_repo = parsed_document_repo
        self.document_repo = document_repo

    # --- Schema CRUD ---

    async def create_schema(
        self,
        project_id: UUID,
        user_id: UUID,
        name: str,
        schema_definition: dict,
        description: str | None = None,
        extraction_target: str = "PER_DOC",
    ) -> ExtractionSchemaResponse:
        try:
            schema = await self.schema_repo.create(
                project_id=project_id, name=name, schema_definition=schema_definition,
                created_by=user_id, description=description, extraction_target=extraction_target,
            )
        except Exception as e:
            if "uq_extraction_schemas_project_name" in str(e):
                raise ConflictError(f"Schema with name '{name}' already exists in this project")
            raise
        return ExtractionSchemaResponse.from_orm_model(schema)

    async def get_schema(self, schema_id: UUID, user_id: UUID) -> ExtractionSchemaResponse:
        schema = await self.schema_repo.get_by_id_for_user(schema_id, user_id)
        if not schema:
            raise NotFoundError(f"Extraction schema {schema_id} not found")
        return ExtractionSchemaResponse.from_orm_model(schema)

    async def list_schemas(self, project_id: UUID, user_id: UUID) -> list[ExtractionSchemaResponse]:
        schemas = await self.schema_repo.list_by_project(project_id, user_id)
        return [ExtractionSchemaResponse.from_orm_model(s) for s in schemas]

    async def update_schema(
        self,
        schema_id: UUID,
        user_id: UUID,
        name: str | None = None,
        description: str | None = None,
        schema_definition: dict | None = None,
        extraction_target: str | None = None,
    ) -> ExtractionSchemaResponse:
        schema = await self.schema_repo.update(
            schema_id=schema_id, user_id=user_id, name=name, description=description,
            schema_definition=schema_definition, extraction_target=extraction_target,
        )
        if not schema:
            raise NotFoundError(f"Extraction schema {schema_id} not found")
        return ExtractionSchemaResponse.from_orm_model(schema)

    async def delete_schema(self, schema_id: UUID, user_id: UUID) -> bool:
        deleted = await self.schema_repo.delete(schema_id, user_id)
        if not deleted:
            raise NotFoundError(f"Extraction schema {schema_id} not found")
        return True

    # --- Extraction ---

    async def run_extraction(
        self,
        parse_run_id: UUID,
        extraction_schema_id: UUID,
        extraction_method: str,
        user_id: UUID,
        config: dict | None = None,
        llm_config=None,           # PromptConfig | None
        user_prompt_template: str | None = None,
    ) -> ExtractionResultResponse:
        """Create a pending extraction result anchored to a CDM ParsedDocument."""
        orm_parsed_doc = await self.parsed_document_repo.get_by_run(parse_run_id)
        if not orm_parsed_doc:
            raise NotFoundError(f"ParsedDocument for parse_run_id {parse_run_id} not found")

        schema = await self.schema_repo.get_by_id(extraction_schema_id)
        if not schema:
            raise NotFoundError(f"Extraction schema {extraction_schema_id} not found")

        document = await self.document_repo.get_by_source_document_for_project(
            source_document_id=orm_parsed_doc.source_document_id,
            project_id=schema.project_id,
        )
        if not document:
            raise NotFoundError(
                f"No document found in project {schema.project_id} "
                f"for source_document {orm_parsed_doc.source_document_id}"
            )

        merged_config = dict(config or {})
        merged_config["extraction_target"] = schema.extraction_target
        if llm_config is not None:
            merged_config["llm_config"] = llm_config.model_dump(by_alias=False, mode="json")
        if user_prompt_template:
            merged_config["user_prompt_template"] = user_prompt_template

        result = await self.result_repo.create(
            document_id=document.id,
            source_parse_run_id=parse_run_id,
            extraction_schema_id=extraction_schema_id,
            schema_definition_snapshot=schema.schema_definition,
            extraction_method=extraction_method,
            created_by=user_id,
            config=merged_config,
        )
        return ExtractionResultResponse.from_orm_model(result)

    # --- Results ---

    async def _reap_stale(self, result):
        if result.status != ExtractionResultStatus.pending:
            return result
        reference_time = result.started_at or result.created_at
        if not reference_time:
            return result
        age = datetime.utcnow() - reference_time.replace(tzinfo=None)
        if age > STALE_TIMEOUT:
            result = await self.result_repo.update_status(
                result.id, ExtractionResultStatus.failed,
                "Extraction job timed out (exceeded 10 minutes)",
            )
        return result

    async def get_extraction_result(self, result_id: UUID) -> ExtractionResultResponse:
        result = await self.result_repo.get_by_id(result_id)
        if not result:
            raise NotFoundError(f"Extraction result {result_id} not found")
        result = await self._reap_stale(result)
        return ExtractionResultResponse.from_orm_model(result)

    async def list_extraction_results(self, document_id: UUID) -> list[ExtractionResultListResponse]:
        results = await self.result_repo.list_by_document(document_id)
        results = [await self._reap_stale(r) for r in results]
        return [ExtractionResultListResponse.from_orm_model(r) for r in results]

    async def get_extractors(self) -> list[ExtractorInfoResponse]:
        """Return full catalogue with configured flag from current credential source.

        BYOK seam: _get_configured_methods_from_settings() is replaced with a
        project_extractor_credentials DB lookup when BYOK is implemented.
        """
        catalogue = get_known_extractors()
        configured = self._get_configured_methods_from_settings()
        return [
            ExtractorInfoResponse(
                extractionMethod=e["extraction_method"],
                name=e["name"],
                description=e["description"],
                configSchema=e.get("config_schema"),
                configured=e["extraction_method"] in configured,
            )
            for e in catalogue
        ]

    def _get_configured_methods_from_settings(self) -> set[str]:
        from app.config import settings
        configured: set[str] = set()
        if getattr(settings, "LLAMA_CLOUD_KEY", None):
            configured.add("llamaextract")
        # "llm" is always configured — ollama_local requires no API key
        configured.add("llm")
        return configured


async def process_extraction(
    extraction_result_id: UUID,
    result_repo: ExtractionResultRepository,
    parsed_document_repo: ParsedDocumentRepository,
    extractor: DataExtractor,
) -> None:
    """Background task: fetch CDM ParsedDocument and run extraction."""
    try:
        await result_repo.set_started(extraction_result_id)

        extraction_result = await result_repo.get_by_id(extraction_result_id)
        if not extraction_result:
            logger.error("Extraction result %s not found during background task", extraction_result_id)
            return

        orm_parsed_doc = await parsed_document_repo.get_by_run(extraction_result.source_parse_run_id)
        if not orm_parsed_doc:
            await result_repo.update_status(
                extraction_result_id,
                ExtractionResultStatus.failed,
                "ParsedDocument not found for parse_run_id",
            )
            return

        cdm_doc = cdm_models.ParsedDocument.model_validate(orm_parsed_doc.content)

        output = await extractor.extract(
            parsed_document=cdm_doc,
            schema=extraction_result.schema_definition_snapshot,
            config=extraction_result.config,
        )

        citations_data = (
            [dataclasses.asdict(c) for c in output.citations]
            if output.citations is not None else None
        )

        await result_repo.update_result(
            result_id=extraction_result_id,
            structured_data=output.structured_data,
            citations=citations_data,
            provider_response_raw=output.provider_response_raw,
            extraction_metadata=output.extraction_metadata,
        )

    except Exception as e:
        logger.exception("Extraction failed for result=%s", extraction_result_id)
        try:
            await result_repo.update_status(
                extraction_result_id,
                ExtractionResultStatus.failed,
                str(e),
            )
        except Exception:
            logger.exception("Failed to update extraction result status for %s", extraction_result_id)
