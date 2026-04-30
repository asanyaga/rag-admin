"""Repository for ParseRun — execution rows."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document as DocumentORM
from app.models.parse_run import ParseRun
from app.models.parsed_document import ParsedDocument
from app.models.source_document import SourceDocument


@dataclass(frozen=True)
class ParseConfigOptionRow:
    """One distinct (parser, parse_config_hash) family available to a project."""
    parser: str
    parse_config_hash: str
    config: dict[str, Any]
    parsed_document_count: int
    has_full_markdown: bool
    latest_parsed_at: datetime


@dataclass
class ParseRunCreate:
    source_document_id: UUID
    parser: str
    representation_kind: str
    config: dict[str, Any]
    config_hash: str
    status: str
    started_at: datetime
    id: UUID | None = None
    parser_version: str | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    cost: dict[str, Any] = field(default_factory=dict)
    input_tokens: int | None = None
    output_tokens: int | None = None
    warnings: list[str] = field(default_factory=list)
    failed_pages: list[int] = field(default_factory=list)
    provider_refs: dict[str, Any] = field(default_factory=dict)
    raw_payload: dict[str, Any] | None = None
    error: str | None = None


class ParseRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, dto: ParseRunCreate) -> ParseRun:
        kwargs: dict[str, Any] = dict(
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
            raw_payload=dto.raw_payload,
            error=dto.error,
        )
        if dto.id is not None:
            kwargs["id"] = dto.id
        row = ParseRun(**kwargs)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get(self, run_id: UUID) -> ParseRun | None:
        result = await self.session.execute(
            select(ParseRun).where(ParseRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_for_source_document(
        self, source_document_id: UUID
    ) -> list[ParseRun]:
        """Return all runs for a source, newest first."""
        result = await self.session.execute(
            select(ParseRun)
            .where(ParseRun.source_document_id == source_document_id)
            .order_by(ParseRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_latest_for_content(
        self,
        *,
        source_document_id: UUID,
        representation_kind: str,
        config_hash: str,
    ) -> ParseRun | None:
        """Point lookup on the unique index (no project-scope check)."""
        result = await self.session.execute(
            select(ParseRun)
            .where(ParseRun.source_document_id == source_document_id)
            .where(ParseRun.representation_kind == representation_kind)
            .where(ParseRun.config_hash == config_hash)
            .order_by(ParseRun.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_for_project(
        self,
        *,
        source_document_id: UUID,
        representation_kind: str,
        config_hash: str,
        project_id: UUID,
    ) -> ParseRun | None:
        """Same-project reuse lookup.

        Only returns a run if source_document_id is referenced by a Document
        row belonging to project_id — enforces the same-project isolation
        policy from the spec (§2.3).
        """
        in_project = (
            select(DocumentORM.source_document_id)
            .where(DocumentORM.project_id == project_id)
            .where(DocumentORM.source_document_id.isnot(None))
        )
        result = await self.session.execute(
            select(ParseRun)
            .where(ParseRun.source_document_id == source_document_id)
            .where(ParseRun.representation_kind == representation_kind)
            .where(ParseRun.config_hash == config_hash)
            .where(ParseRun.source_document_id.in_(in_project))
            .order_by(ParseRun.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_distinct_configs_for_project(
        self, project_id: UUID
    ) -> list[ParseConfigOptionRow]:
        """List distinct (parser, config_hash) families with parsed_documents in a project.

        Joins parsed_documents → parse_runs → source_documents → documents and groups by
        (parser, config_hash), returning one row per family with aggregate counts and the
        newest finished_at across the family. Only succeeded runs are included.
        """
        markdown_present = case(
            (ParsedDocument.full_markdown.isnot(None), 1), else_=0
        )

        agg_stmt = (
            select(
                ParseRun.parser.label("parser"),
                ParseRun.config_hash.label("parse_config_hash"),
                func.count(ParsedDocument.parse_run_id).label("parsed_document_count"),
                func.coalesce(func.max(markdown_present), 0).label("has_full_markdown_int"),
                func.max(ParseRun.finished_at).label("latest_parsed_at"),
            )
            .select_from(ParsedDocument)
            .join(ParseRun, ParseRun.id == ParsedDocument.parse_run_id)
            .join(SourceDocument, ParseRun.source_document_id == SourceDocument.id)
            .join(DocumentORM, DocumentORM.source_document_id == SourceDocument.id)
            .where(ParseRun.status == "succeeded")
            .where(DocumentORM.project_id == project_id)
            .group_by(ParseRun.parser, ParseRun.config_hash)
            .order_by(func.max(ParseRun.finished_at).desc())
        )
        agg_rows = (await self.session.execute(agg_stmt)).all()
        if not agg_rows:
            return []

        # Fetch one representative config per (parser, config_hash). The config_hash is
        # deterministically derived from the config dict, so any row's config is correct.
        configs: dict[tuple[str, str], dict[str, Any]] = {}
        for row in agg_rows:
            key = (row.parser, row.parse_config_hash)
            if key in configs:
                continue
            cfg = (await self.session.execute(
                select(ParseRun.config)
                .where(ParseRun.parser == row.parser)
                .where(ParseRun.config_hash == row.parse_config_hash)
                .limit(1)
            )).scalar()
            configs[key] = cfg or {}

        return [
            ParseConfigOptionRow(
                parser=row.parser,
                parse_config_hash=row.parse_config_hash,
                config=configs[(row.parser, row.parse_config_hash)],
                parsed_document_count=row.parsed_document_count,
                has_full_markdown=bool(row.has_full_markdown_int),
                latest_parsed_at=row.latest_parsed_at,
            )
            for row in agg_rows
        ]

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
