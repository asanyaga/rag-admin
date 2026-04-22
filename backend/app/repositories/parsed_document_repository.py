"""Repository for ParsedDocumentORM — content blob layer."""
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parsed_document import ParsedDocumentORM


@dataclass
class ParsedDocumentCreate:
    parse_run_id: UUID
    source_document_id: UUID
    full_text: str | None
    full_markdown: str | None
    page_count: int
    block_count: int
    content: dict[str, Any]


class ParsedDocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, dto: ParsedDocumentCreate) -> ParsedDocumentORM:
        row = ParsedDocumentORM(
            parse_run_id=dto.parse_run_id,
            source_document_id=dto.source_document_id,
            full_text=dto.full_text,
            full_markdown=dto.full_markdown,
            page_count=dto.page_count,
            block_count=dto.block_count,
            content=dto.content,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_by_run(self, parse_run_id: UUID) -> ParsedDocumentORM | None:
        result = await self.session.execute(
            select(ParsedDocumentORM).where(ParsedDocumentORM.parse_run_id == parse_run_id)
        )
        return result.scalar_one_or_none()
