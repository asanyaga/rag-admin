"""Agent service — orchestrates the receipt processing pipeline."""
import logging
from uuid import UUID, uuid4

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command

from app.models.agent_receipt import AgentReceiptStatus
from app.repositories.agent_receipt_repository import AgentReceiptRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.extraction_schema_repository import ExtractionSchemaRepository
from app.schemas.agent import AgentReceiptResponse, AgentReceiptListItem
from app.services.agent.graph import build_receipt_graph
from app.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class AgentService:
    """Service for the LangGraph receipt processing pipeline."""

    def __init__(
        self,
        receipt_repo: AgentReceiptRepository,
        document_repo: DocumentRepository,
        schema_repo: ExtractionSchemaRepository,
        checkpointer: AsyncPostgresSaver,
    ):
        self.receipt_repo = receipt_repo
        self.document_repo = document_repo
        self.schema_repo = schema_repo
        self.checkpointer = checkpointer

    async def start_processing(
        self,
        project_id: UUID,
        document_id: UUID,
        extraction_schema_id: UUID,
        user_id: UUID,
    ) -> AgentReceiptResponse:
        """Start processing a receipt through the extract -> review -> export pipeline."""
        # Validate document
        document = await self.document_repo.get_by_id_unscoped(document_id)
        if not document:
            raise NotFoundError(f"Document {document_id} not found")

        file_path = document.source_metadata.get("file_path")
        if not file_path:
            raise NotFoundError("Document has no file path")

        # Validate schema
        schema = await self.schema_repo.get_by_id(extraction_schema_id)
        if not schema:
            raise NotFoundError(f"Extraction schema {extraction_schema_id} not found")

        # Create receipt record
        receipt = await self.receipt_repo.create(
            project_id=project_id,
            document_id=document_id,
            extraction_schema_id=extraction_schema_id,
            created_by=user_id,
        )

        # Update status to extracting
        await self.receipt_repo.update_status(receipt.id, AgentReceiptStatus.extracting)

        # Build and run graph (synchronous — runs extract then interrupts at review)
        thread_id = str(uuid4())
        compiled = build_receipt_graph(checkpointer=self.checkpointer)

        initial_state = {
            "receipt_id": str(receipt.id),
            "document_id": str(document_id),
            "file_path": file_path,
            "extraction_schema_id": str(extraction_schema_id),
            "schema_definition": schema.schema_definition,
            "extraction_config": {},
            "current_step": "extract",
        }

        config = {"configurable": {"thread_id": thread_id}}

        try:
            # This runs extract_node, then interrupts at review_node
            result = await compiled.ainvoke(initial_state, config=config)

            # Check for extraction error
            if result.get("error"):
                await self.receipt_repo.update_status(
                    receipt.id,
                    AgentReceiptStatus.failed,
                    result["error"],
                )
                receipt = await self.receipt_repo.get_by_id(receipt.id)
                return AgentReceiptResponse.from_orm_model(receipt)

            # Graph interrupted at review — update receipt with extracted data
            # When interrupt() is called, ainvoke returns the state at that point
            extracted_data = result.get("extracted_data", {})
            receipt = await self.receipt_repo.update_extracted_data(
                receipt.id,
                extracted_data=extracted_data,
                thread_id=thread_id,
            )

        except Exception as e:
            logger.exception("Graph execution failed for receipt %s", receipt.id)
            await self.receipt_repo.update_status(
                receipt.id,
                AgentReceiptStatus.failed,
                str(e),
            )
            receipt = await self.receipt_repo.get_by_id(receipt.id)

        return AgentReceiptResponse.from_orm_model(receipt)

    async def get_receipt(self, receipt_id: UUID) -> AgentReceiptResponse:
        """Get a receipt by ID."""
        receipt = await self.receipt_repo.get_by_id(receipt_id)
        if not receipt:
            raise NotFoundError(f"Agent receipt {receipt_id} not found")
        return AgentReceiptResponse.from_orm_model(receipt)

    async def list_receipts(self, project_id: UUID) -> list[AgentReceiptListItem]:
        """List receipts for a project."""
        receipts = await self.receipt_repo.list_by_project(project_id)
        return [AgentReceiptListItem.from_orm_model(r) for r in receipts]

    async def submit_review(
        self,
        receipt_id: UUID,
        action: str,
        data: dict | None = None,
    ) -> AgentReceiptResponse:
        """Resume the graph with review decision."""
        receipt = await self.receipt_repo.get_by_id(receipt_id)
        if not receipt:
            raise NotFoundError(f"Agent receipt {receipt_id} not found")

        if receipt.status != AgentReceiptStatus.reviewing:
            raise ValueError(f"Receipt {receipt_id} is not in reviewing status")

        if not receipt.thread_id:
            raise ValueError(f"Receipt {receipt_id} has no thread_id")

        compiled = build_receipt_graph(checkpointer=self.checkpointer)
        config = {"configurable": {"thread_id": receipt.thread_id}}

        try:
            # Resume graph with review decision
            result = await compiled.ainvoke(
                Command(resume={"action": action, "data": data}),
                config=config,
            )

            if action == "reject":
                await self.receipt_repo.update_status(
                    receipt_id,
                    AgentReceiptStatus.failed,
                    "Rejected by reviewer",
                )
                receipt = await self.receipt_repo.get_by_id(receipt_id)
            else:
                # approve or edit — export_node ran
                final_data = result.get("reviewed_data") or receipt.extracted_data
                receipt = await self.receipt_repo.update_reviewed_data(
                    receipt_id,
                    reviewed_data=final_data,
                    status=AgentReceiptStatus.exported,
                )

        except Exception as e:
            logger.exception("Review submission failed for receipt %s", receipt_id)
            await self.receipt_repo.update_status(
                receipt_id,
                AgentReceiptStatus.failed,
                str(e),
            )
            receipt = await self.receipt_repo.get_by_id(receipt_id)

        return AgentReceiptResponse.from_orm_model(receipt)
