"""Parse service — manages parse results and background parsing."""
import logging
from datetime import datetime, timedelta
from uuid import UUID

from app.models import DocumentStatus
from app.models.parse_result import ParseResultStatus
from app.ports.document_parsing import DocumentParser
from app.ports import StorageService
from app.repositories.document_repository import DocumentRepository
from app.repositories.parse_result_repository import ParseResultRepository
from app.schemas.parse_result import (
    ParseResultResponse,
    ParseResultListResponse,
    ParserInfoResponse,
)
from app.adapters.parsing.registry import get_available_parsers
from app.services.exceptions import NotFoundError
from app.utils.parse_diagnostics import compute_diagnostics

logger = logging.getLogger(__name__)

STALE_TIMEOUT = timedelta(minutes=10)


class ParseService:
    """Service for parse result operations."""

    def __init__(
        self,
        parse_result_repo: ParseResultRepository,
        document_repo: DocumentRepository,
    ):
        self.parse_result_repo = parse_result_repo
        self.document_repo = document_repo

    async def create_parse_result(
        self,
        document_id: UUID,
        user_id: UUID,
        parser_type: str,
        parser_config: dict | None = None,
    ) -> ParseResultResponse:
        """Create a pending parse result row."""
        # Verify document exists
        document = await self.document_repo.get_by_id_unscoped(document_id)
        if not document:
            raise NotFoundError(f"Document {document_id} not found")

        parse_result = await self.parse_result_repo.create(
            document_id=document_id,
            parser_type=parser_type,
            created_by=user_id,
            parser_config=parser_config,
        )
        return ParseResultResponse.from_orm_model(parse_result)

    async def _reap_stale(self, parse_result):
        """Mark a pending parse result as failed if it has exceeded the stale timeout.

        Uses started_at if available, otherwise falls back to created_at so that
        jobs which crash before set_started() are still reaped.
        """
        if parse_result.status != ParseResultStatus.pending:
            return parse_result

        reference_time = parse_result.started_at or parse_result.created_at
        if not reference_time:
            return parse_result

        age = datetime.utcnow() - reference_time.replace(tzinfo=None)
        if age > STALE_TIMEOUT:
            parse_result = await self.parse_result_repo.update_status(
                parse_result.id,
                ParseResultStatus.failed,
                "Parse job timed out (exceeded 10 minutes)",
            )
            # Also update document status so the document polling stops
            try:
                await self.document_repo.update_status(
                    parse_result.document_id,
                    DocumentStatus.failed,
                    "Parse job timed out",
                )
            except Exception:
                logger.warning("Failed to update document status for stale parse result %s", parse_result.id)
        return parse_result

    async def get_parse_result(self, parse_result_id: UUID) -> ParseResultResponse:
        """Get a parse result by ID, with stale job detection."""
        parse_result = await self.parse_result_repo.get_by_id(parse_result_id)
        if not parse_result:
            raise NotFoundError(f"Parse result {parse_result_id} not found")

        parse_result = await self._reap_stale(parse_result)
        return ParseResultResponse.from_orm_model(parse_result)

    async def list_parse_results(self, document_id: UUID) -> list[ParseResultListResponse]:
        """List all parse results for a document."""
        results = await self.parse_result_repo.list_by_document(document_id)
        results = [await self._reap_stale(r) for r in results]
        return [ParseResultListResponse.from_orm_model(r) for r in results]

    async def get_parsers(self) -> list[ParserInfoResponse]:
        """Get list of available parsers."""
        parsers = get_available_parsers()
        return [
            ParserInfoResponse(
                parserType=p["parser_type"],
                name=p["name"],
                description=p["description"],
                supportedFileTypes=p["supported_file_types"],
                configSchema=p.get("config_schema"),
            )
            for p in parsers
        ]


async def process_document_parsing(
    parse_result_id: UUID,
    parse_result_repo: ParseResultRepository,
    document_repo: DocumentRepository,
    storage_service: StorageService,
    parser: DocumentParser,
) -> None:
    """Background task to parse a document.

    Args:
        parse_result_id: Parse result UUID
        parse_result_repo: Parse result repository
        document_repo: Document repository
        storage_service: Storage service
        parser: Parser adapter instance
    """
    document_id = None
    try:
        # Mark as started
        await parse_result_repo.set_started(parse_result_id)

        # Get parse result to find document
        parse_result = await parse_result_repo.get_by_id(parse_result_id)
        if not parse_result:
            logger.error("Parse result %s not found during background task", parse_result_id)
            return

        document_id = parse_result.document_id

        # Get document
        document = await document_repo.get_by_id_unscoped(parse_result.document_id)
        if not document:
            await parse_result_repo.update_status(
                parse_result_id,
                ParseResultStatus.failed,
                "Document not found",
            )
            return

        # Get file path
        file_path = document.source_metadata.get("file_path")
        if not file_path:
            msg = "Missing file path in document metadata"
            await parse_result_repo.update_status(
                parse_result_id,
                ParseResultStatus.failed,
                msg,
            )
            await document_repo.update_status(
                document_id,
                DocumentStatus.failed,
                msg,
            )
            return

        # Parse
        parse_output = await parser.parse(file_path, parse_result.parser_config)

        # Compute diagnostics
        diagnostics = compute_diagnostics(parse_output.raw_text, parse_output.markdown)

        # Update parse result with completed data
        await parse_result_repo.update_result(
            parse_result_id=parse_result_id,
            raw_text=parse_output.raw_text,
            fidelity=parse_output.fidelity,
            markdown=parse_output.markdown,
            pages=parse_output.pages,
            document_structure=parse_output.document_structure,
            diagnostics=diagnostics,
            metadata=parse_output.metadata,
            parser_config=parse_output.parser_config,
        )

        # Also write raw_text to documents.extracted_text for backward compat
        await document_repo.update_extraction(
            document_id=parse_result.document_id,
            extracted_text=parse_output.raw_text,
            processing_metadata={"parser_type": parse_output.parser_type, **parse_output.metadata},
            status=DocumentStatus.ready,
        )

    except Exception as e:
        logger.exception("Parse failed for parse_result=%s document=%s", parse_result_id, document_id)
        try:
            await parse_result_repo.update_status(
                parse_result_id,
                ParseResultStatus.failed,
                str(e),
            )
        except Exception:
            logger.exception("Failed to update parse_result status for %s", parse_result_id)
        # Also mark document as failed so the UI stops polling
        if document_id:
            try:
                await document_repo.update_status(
                    document_id,
                    DocumentStatus.failed,
                    f"Parse failed: {e}",
                )
            except Exception:
                logger.exception("Failed to update document status for %s", document_id)
