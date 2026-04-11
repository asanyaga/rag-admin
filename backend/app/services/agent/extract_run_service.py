"""Extract run service — resolves document/schema inputs and delegates to FlowRunService."""
import logging
from uuid import UUID

from app.repositories.document_repository import DocumentRepository
from app.repositories.extraction_schema_repository import ExtractionSchemaRepository
from app.schemas.agent import FlowRunResponse
from app.services.agent.flow_run_service import FlowRunService
from app.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class ExtractRunService:
    """Thin service that resolves extraction-specific inputs into a generic initial state."""

    def __init__(
        self,
        flow_run_service: FlowRunService,
        document_repo: DocumentRepository,
        schema_repo: ExtractionSchemaRepository,
    ):
        self.flow_run_service = flow_run_service
        self.document_repo = document_repo
        self.schema_repo = schema_repo

    async def start_extract_run(
        self,
        project_id: UUID,
        flow_definition_id: UUID,
        document_id: UUID,
        extraction_schema_id: UUID,
        user_id: UUID,
    ) -> FlowRunResponse:
        """Resolve document + schema into initial state and start a flow run."""
        # Validate and resolve document
        document = await self.document_repo.get_by_id_unscoped(document_id)
        if not document:
            raise NotFoundError(f"Document {document_id} not found")

        file_path = document.source_metadata.get("file_path")
        if not file_path:
            raise NotFoundError("Document has no file path")

        # Validate and resolve schema
        schema = await self.schema_repo.get_by_id(extraction_schema_id)
        if not schema:
            raise NotFoundError(f"Extraction schema {extraction_schema_id} not found")

        # Build initial state
        initial_state = {
            "document_id": str(document_id),
            "file_path": file_path,
            "extraction_schema_id": str(extraction_schema_id),
            "schema_definition": schema.schema_definition,
            "extraction_config": {},
            "current_step": "extract",
        }

        return await self.flow_run_service.start_run(
            project_id=project_id,
            flow_definition_id=flow_definition_id,
            initial_state=initial_state,
            user_id=user_id,
        )
