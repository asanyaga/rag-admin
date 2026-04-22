"""Repository for ParseRun — execution rows."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_run import ParseRun


@dataclass
class ParseRunCreate:
    source_document_id: UUID
    parser: str
    representation_kind: str
    config: dict[str, Any]
    config_hash: str
    status: str
    started_at: datetime
    parser_version: str | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    cost: dict[str, Any] = field(default_factory=dict)
    input_tokens: int | None = None
    output_tokens: int | None = None
    warnings: list[str] = field(default_factory=list)
    failed_pages: list[int] = field(default_factory=list)
    provider_refs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class ParseRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, dto: ParseRunCreate) -> ParseRun:
        row = ParseRun(
            source_document_id=dto.source_document_id,
            parser=dto.parser,
            parser_version=dto.parser_version,
            representation_kind=dto.representation_kind,
            config=dto.config,
            config_hash=dto.config_hash,
            status=dto.status,
            started_at=dto.started_at,
            finished_at=dto.finished_at,
            duration_ms=dto.duration_ms,
            cost=dto.cost,
            input_tokens=dto.input_tokens,
            output_tokens=dto.output_tokens,
            warnings=dto.warnings,
            failed_pages=dto.failed_pages,
            provider_refs=dto.provider_refs,
            error=dto.error,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get(self, run_id: UUID) -> ParseRun | None:
        result = await self.session.execute(
            select(ParseRun).where(ParseRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_for_content(
        self,
        *,
        source_document_id: UUID,
        representation_kind: str,
        config_hash: str,
    ) -> ParseRun | None:
        """Point lookup on the unique index."""
        result = await self.session.execute(
            select(ParseRun)
            .where(ParseRun.source_document_id == source_document_id)
            .where(ParseRun.representation_kind == representation_kind)
            .where(ParseRun.config_hash == config_hash)
            .order_by(ParseRun.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        run_id: UUID,
        *,
        status: str,
        finished_at: datetime | None = None,
        duration_ms: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
        failed_pages: list[int] | None = None,
        provider_refs: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ParseRun:
        run = await self.get(run_id)
        if run is None:
            raise ValueError(f"ParseRun {run_id} not found")
        run.status = status
        if finished_at is not None:
            run.finished_at = finished_at
        if duration_ms is not None:
            run.duration_ms = duration_ms
        if input_tokens is not None:
            run.input_tokens = input_tokens
        if output_tokens is not None:
            run.output_tokens = output_tokens
        if cost is not None:
            run.cost = cost
        if warnings is not None:
            run.warnings = warnings
        if failed_pages is not None:
            run.failed_pages = failed_pages
        if provider_refs is not None:
            run.provider_refs = provider_refs
        if error is not None:
            run.error = error
        await self.session.commit()
        await self.session.refresh(run)
        return run
