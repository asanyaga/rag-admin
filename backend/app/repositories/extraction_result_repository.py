"""Repository for extraction result data access."""
from uuid import UUID
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_result import ExtractionResult, ExtractionResultStatus


class ExtractionResultRepository:
    """Repository for extraction result data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        document_id: UUID,
        extraction_schema_id: UUID,
        schema_definition_snapshot: dict,
        extraction_method: str,
        created_by: UUID,
        config: dict | None = None,
        source_parse_run_id: UUID | None = None,
    ) -> ExtractionResult:
        """Create a new pending extraction result."""
        result = ExtractionResult(
            document_id=document_id,
            extraction_schema_id=extraction_schema_id,
            schema_definition_snapshot=schema_definition_snapshot,
            extraction_method=extraction_method,
            config=config,
            created_by=created_by,
            source_parse_run_id=source_parse_run_id,
            status=ExtractionResultStatus.pending,
        )
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def get_by_id(self, result_id: UUID) -> ExtractionResult | None:
        """Get an extraction result by ID (unscoped, for background tasks too)."""
        result = await self.session.execute(
            select(ExtractionResult).where(ExtractionResult.id == result_id)
        )
        return result.scalar_one_or_none()

    async def list_by_document(self, document_id: UUID) -> list[ExtractionResult]:
        """List all extraction results for a document."""
        result = await self.session.execute(
            select(ExtractionResult)
            .where(ExtractionResult.document_id == document_id)
            .order_by(ExtractionResult.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        result_id: UUID,
        status: ExtractionResultStatus,
        status_message: str | None = None,
    ) -> ExtractionResult | None:
        """Update extraction result status."""
        extraction_result = await self.get_by_id(result_id)
        if not extraction_result:
            return None

        extraction_result.status = status
        extraction_result.status_message = status_message

        await self.session.commit()
        await self.session.refresh(extraction_result)
        return extraction_result

    async def update_result(
        self,
        result_id: UUID,
        structured_data: dict,
        extraction_metadata: dict | None = None,
        citations: list[dict] | None = None,
        provider_response_raw: dict | None = None,
    ) -> ExtractionResult | None:
        """Update extraction result with completed data."""
        extraction_result = await self.get_by_id(result_id)
        if not extraction_result:
            return None

        extraction_result.structured_data = structured_data
        extraction_result.extraction_metadata = extraction_metadata
        extraction_result.citations = citations
        extraction_result.provider_response_raw = provider_response_raw
        extraction_result.status = ExtractionResultStatus.completed
        extraction_result.status_message = None

        await self.session.commit()
        await self.session.refresh(extraction_result)
        return extraction_result

    async def set_started(self, result_id: UUID) -> ExtractionResult | None:
        """Mark an extraction result as started."""
        extraction_result = await self.get_by_id(result_id)
        if not extraction_result:
            return None

        extraction_result.started_at = datetime.utcnow()

        await self.session.commit()
        await self.session.refresh(extraction_result)
        return extraction_result
