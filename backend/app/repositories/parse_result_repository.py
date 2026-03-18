"""Repository for parse result data access."""
from uuid import UUID
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_result import ParseResult, ParseResultStatus


class ParseResultRepository:
    """Repository for parse result data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        document_id: UUID,
        parser_type: str,
        created_by: UUID,
        parser_config: dict | None = None,
    ) -> ParseResult:
        """Create a new pending parse result."""
        parse_result = ParseResult(
            document_id=document_id,
            parser_type=parser_type,
            created_by=created_by,
            parser_config=parser_config,
            status=ParseResultStatus.pending,
        )
        self.session.add(parse_result)
        await self.session.commit()
        await self.session.refresh(parse_result)
        return parse_result

    async def get_by_id(self, parse_result_id: UUID) -> ParseResult | None:
        """Get a parse result by ID (unscoped, for background tasks too)."""
        result = await self.session.execute(
            select(ParseResult).where(ParseResult.id == parse_result_id)
        )
        return result.scalar_one_or_none()

    async def list_by_document(self, document_id: UUID) -> list[ParseResult]:
        """List all parse results for a document."""
        result = await self.session.execute(
            select(ParseResult)
            .where(ParseResult.document_id == document_id)
            .order_by(ParseResult.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        parse_result_id: UUID,
        status: ParseResultStatus,
        status_message: str | None = None,
    ) -> ParseResult | None:
        """Update parse result status."""
        parse_result = await self.get_by_id(parse_result_id)
        if not parse_result:
            return None

        parse_result.status = status
        parse_result.status_message = status_message

        await self.session.commit()
        await self.session.refresh(parse_result)
        return parse_result

    async def update_result(
        self,
        parse_result_id: UUID,
        raw_text: str,
        fidelity: str,
        markdown: str | None = None,
        pages: list[dict] | None = None,
        document_structure: dict | None = None,
        diagnostics: dict | None = None,
        metadata: dict | None = None,
        parser_config: dict | None = None,
    ) -> ParseResult | None:
        """Update parse result with completed data."""
        parse_result = await self.get_by_id(parse_result_id)
        if not parse_result:
            return None

        parse_result.raw_text = raw_text
        parse_result.fidelity = fidelity
        parse_result.markdown = markdown
        parse_result.pages = pages
        parse_result.document_structure = document_structure
        parse_result.diagnostics = diagnostics
        parse_result.metadata_ = metadata
        if parser_config is not None:
            parse_result.parser_config = parser_config
        parse_result.status = ParseResultStatus.completed
        parse_result.status_message = None

        await self.session.commit()
        await self.session.refresh(parse_result)
        return parse_result

    async def set_started(self, parse_result_id: UUID) -> ParseResult | None:
        """Mark a parse result as started."""
        parse_result = await self.get_by_id(parse_result_id)
        if not parse_result:
            return None

        parse_result.started_at = datetime.utcnow()

        await self.session.commit()
        await self.session.refresh(parse_result)
        return parse_result
