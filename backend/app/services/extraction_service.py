"""Extraction service — manages extraction schemas, results, and background extraction."""
import logging
from datetime import datetime, timedelta
from uuid import UUID

from app.models.extraction_result import ExtractionResultStatus
from app.ports.data_extraction import DataExtractor
from app.ports import StorageService
from app.repositories.document_repository import DocumentRepository
from app.repositories.extraction_schema_repository import ExtractionSchemaRepository
from app.repositories.extraction_result_repository import ExtractionResultRepository
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
        document_repo: DocumentRepository,
    ):
        self.schema_repo = schema_repo
        self.result_repo = result_repo
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
        """Create an extraction schema."""
        try:
            schema = await self.schema_repo.create(
                project_id=project_id,
                name=name,
                schema_definition=schema_definition,
                created_by=user_id,
                description=description,
                extraction_target=extraction_target,
            )
        except Exception as e:
            if "uq_extraction_schemas_project_name" in str(e):
                raise ConflictError(f"Schema with name '{name}' already exists in this project")
            raise
        return ExtractionSchemaResponse.from_orm_model(schema)

    async def get_schema(self, schema_id: UUID, user_id: UUID) -> ExtractionSchemaResponse:
        """Get an extraction schema by ID."""
        schema = await self.schema_repo.get_by_id_for_user(schema_id, user_id)
        if not schema:
            raise NotFoundError(f"Extraction schema {schema_id} not found")
        return ExtractionSchemaResponse.from_orm_model(schema)

    async def list_schemas(
        self, project_id: UUID, user_id: UUID
    ) -> list[ExtractionSchemaResponse]:
        """List extraction schemas for a project."""
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
        """Update an extraction schema."""
        schema = await self.schema_repo.update(
            schema_id=schema_id,
            user_id=user_id,
            name=name,
            description=description,
            schema_definition=schema_definition,
            extraction_target=extraction_target,
        )
        if not schema:
            raise NotFoundError(f"Extraction schema {schema_id} not found")
        return ExtractionSchemaResponse.from_orm_model(schema)

    async def delete_schema(self, schema_id: UUID, user_id: UUID) -> bool:
        """Delete an extraction schema."""
        deleted = await self.schema_repo.delete(schema_id, user_id)
        if not deleted:
            raise NotFoundError(f"Extraction schema {schema_id} not found")
        return True

    # --- Extraction ---

    async def run_extraction(
        self,
        document_id: UUID,
        extraction_schema_id: UUID,
        extraction_method: str,
        user_id: UUID,
        config: dict | None = None,
    ) -> ExtractionResultResponse:
        """Create a pending extraction result and validate inputs."""
        # Verify document exists
        document = await self.document_repo.get_by_id_unscoped(document_id)
        if not document:
            raise NotFoundError(f"Document {document_id} not found")

        # Verify schema exists
        schema = await self.schema_repo.get_by_id(extraction_schema_id)
        if not schema:
            raise NotFoundError(f"Extraction schema {extraction_schema_id} not found")

        # Merge extraction_target into config for the adapter
        merged_config = dict(config or {})
        merged_config["extraction_target"] = schema.extraction_target

        result = await self.result_repo.create(
            document_id=document_id,
            extraction_schema_id=extraction_schema_id,
            schema_definition_snapshot=schema.schema_definition,
            extraction_method=extraction_method,
            created_by=user_id,
            config=merged_config,
        )
        return ExtractionResultResponse.from_orm_model(result)

    # --- Results ---

    async def _reap_stale(self, result):
        """Mark pending extraction result as failed if stale."""
        if result.status != ExtractionResultStatus.pending:
            return result

        reference_time = result.started_at or result.created_at
        if not reference_time:
            return result

        age = datetime.utcnow() - reference_time.replace(tzinfo=None)
        if age > STALE_TIMEOUT:
            result = await self.result_repo.update_status(
                result.id,
                ExtractionResultStatus.failed,
                "Extraction job timed out (exceeded 10 minutes)",
            )
        return result

    async def get_extraction_result(
        self, result_id: UUID
    ) -> ExtractionResultResponse:
        """Get an extraction result by ID, with stale job detection."""
        result = await self.result_repo.get_by_id(result_id)
        if not result:
            raise NotFoundError(f"Extraction result {result_id} not found")

        result = await self._reap_stale(result)
        return ExtractionResultResponse.from_orm_model(result)

    async def list_extraction_results(
        self, document_id: UUID
    ) -> list[ExtractionResultListResponse]:
        """List extraction results for a document."""
        results = await self.result_repo.list_by_document(document_id)
        results = [await self._reap_stale(r) for r in results]
        return [ExtractionResultListResponse.from_orm_model(r) for r in results]

    async def get_extractors(self) -> list[ExtractorInfoResponse]:
        """Get list of available extractors."""
        extractors = get_known_extractors()
        return [
            ExtractorInfoResponse(
                extractionMethod=e["extraction_method"],
                name=e["name"],
                description=e["description"],
                configSchema=e.get("config_schema"),
            )
            for e in extractors
        ]


async def process_extraction(
    extraction_result_id: UUID,
    result_repo: ExtractionResultRepository,
    document_repo: DocumentRepository,
    storage_service: StorageService,
    extractor: DataExtractor,
) -> None:
    """Background task to extract structured data from a document."""
    try:
        # Mark as started
        await result_repo.set_started(extraction_result_id)

        # Get extraction result
        extraction_result = await result_repo.get_by_id(extraction_result_id)
        if not extraction_result:
            logger.error("Extraction result %s not found during background task", extraction_result_id)
            return

        # Get document
        document = await document_repo.get_by_id_unscoped(extraction_result.document_id)
        if not document:
            await result_repo.update_status(
                extraction_result_id,
                ExtractionResultStatus.failed,
                "Document not found",
            )
            return

        # Get file path
        file_path = document.source_metadata.get("file_path")
        if not file_path:
            await result_repo.update_status(
                extraction_result_id,
                ExtractionResultStatus.failed,
                "Missing file path in document metadata",
            )
            return

        # Run extraction
        output = await extractor.extract(
            file_path=file_path,
            schema=extraction_result.schema_definition_snapshot,
            config=extraction_result.config,
        )

        # Update result with extracted data
        await result_repo.update_result(
            result_id=extraction_result_id,
            structured_data=output.structured_data,
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
