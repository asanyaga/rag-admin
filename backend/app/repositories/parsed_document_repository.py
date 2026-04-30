"""Repository for ParsedDocument — content blob layer."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document as DocumentORM
from app.models.parse_run import ParseRun
from app.models.parsed_document import ParsedDocument
from app.models.source_document import SourceDocument


Representation = Literal["full_text", "full_markdown", "block"]


@dataclass
class ParsedDocumentCreate:
    parse_run_id: UUID
    source_document_id: UUID
    full_text: str | None
    full_markdown: str | None
    page_count: int
    block_count: int
    content: dict[str, Any]


@dataclass(frozen=True)
class ParsedDocValidationRow:
    parse_run_id: UUID
    parser: str
    parse_config_hash: str
    run_status: str
    full_markdown: str | None
    block_count: int


@dataclass(frozen=True)
class ParsedDocumentListRow:
    """One parsed-document picker row.

    `parse_run_id` is the parsed-document handle under the current 1:1 schema
    (parsed_documents.parse_run_id is its primary key). When parsed_documents grows a
    distinct `id` column for derived parsed-docs, the API surface keeps the same shape;
    the wire value just shifts from parse_run_id-of-this-parsed-doc to id-of-this-parsed-doc.
    """
    parse_run_id: UUID
    parser: str
    parse_config_hash: str
    source_document_id: UUID
    source_filename: str | None
    has_full_markdown: bool
    block_count: int
    parsed_at: datetime


class ParsedDocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, dto: ParsedDocumentCreate) -> ParsedDocument:
        row = ParsedDocument(
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

    async def get_by_run(self, parse_run_id: UUID) -> ParsedDocument | None:
        result = await self.session.execute(
            select(ParsedDocument).where(ParsedDocument.parse_run_id == parse_run_id)
        )
        return result.scalar_one_or_none()

    async def get_for_validation(
        self,
        *,
        parsed_document_ids: list[UUID],
        project_id: UUID,
    ) -> list[ParsedDocValidationRow]:
        """Return validation-row data for parsed-docs scoped to a project.

        Joins parsed_doc → parse_run → document on (source_document_id, project_id),
        so a parsed-doc whose source_document is referenced only by another
        project's Document is silently filtered out (treated as not-in-project).
        """
        if not parsed_document_ids:
            return []
        stmt = (
            select(
                ParsedDocument.parse_run_id,
                ParseRun.parser,
                ParseRun.config_hash,
                ParseRun.status,
                ParsedDocument.full_markdown,
                ParsedDocument.block_count,
            )
            .join(ParseRun, ParseRun.id == ParsedDocument.parse_run_id)
            .join(DocumentORM, DocumentORM.source_document_id == ParseRun.source_document_id)
            .where(
                ParsedDocument.parse_run_id.in_(parsed_document_ids),
                DocumentORM.project_id == project_id,
            )
            .distinct()  # in case multiple Documents share a source_document
        )
        result = await self.session.execute(stmt)
        return [
            ParsedDocValidationRow(
                parse_run_id=row.parse_run_id,
                parser=row.parser,
                parse_config_hash=row.config_hash,
                run_status=row.status,
                full_markdown=row.full_markdown,
                block_count=row.block_count,
            )
            for row in result.all()
        ]

    async def list_for_project(
        self,
        project_id: UUID,
        *,
        parser: str | None = None,
        parse_config_hash: str | None = None,
        representation: Representation | None = None,
        latest_per_source: bool = True,
    ) -> list[ParsedDocumentListRow]:
        """List parsed-documents for the project's documents, newest first.

        Filters:
          - `parser` + `parse_config_hash` restrict to one (parser, config_hash) family.
          - `representation`: keep parsed-docs that populate the named segment
            (`full_markdown`, `full_text`, or `block`). `full_text` and `block` are
            invariants on every parsed_doc and pass-through; `full_markdown` is filtered
            on `full_markdown IS NOT NULL`.
          - `latest_per_source=True` (default) keeps only the newest parse_run per
            `source_document_id`. Set False to expose every successful run in the family
            for non-determinism debugging.
        """
        inner = (
            select(
                ParsedDocument.parse_run_id.label("parse_run_id"),
                ParseRun.parser.label("parser"),
                ParseRun.config_hash.label("parse_config_hash"),
                ParseRun.source_document_id.label("source_document_id"),
                ParseRun.finished_at.label("parsed_at"),
                SourceDocument.filename.label("source_filename"),
                ParsedDocument.full_markdown.label("full_markdown_value"),
                ParsedDocument.block_count.label("block_count"),
            )
            .select_from(ParsedDocument)
            .join(ParseRun, ParseRun.id == ParsedDocument.parse_run_id)
            .join(SourceDocument, ParseRun.source_document_id == SourceDocument.id)
            .join(DocumentORM, DocumentORM.source_document_id == SourceDocument.id)
            .where(ParseRun.status == "succeeded")
            .where(DocumentORM.project_id == project_id)
        )
        if parser is not None:
            inner = inner.where(ParseRun.parser == parser)
        if parse_config_hash is not None:
            inner = inner.where(ParseRun.config_hash == parse_config_hash)
        if representation == "full_markdown":
            inner = inner.where(ParsedDocument.full_markdown.isnot(None))
        # full_text / block: invariants — no extra filter needed.

        if latest_per_source:
            rn = (
                func.row_number()
                .over(
                    partition_by=ParseRun.source_document_id,
                    order_by=ParseRun.finished_at.desc(),
                )
                .label("rn")
            )
            sub = inner.add_columns(rn).subquery()
            stmt = (
                select(sub)
                .where(sub.c.rn == 1)
                .order_by(sub.c.parsed_at.desc())
            )
        else:
            stmt = inner.order_by(ParseRun.finished_at.desc())

        rows = (await self.session.execute(stmt)).all()
        return [
            ParsedDocumentListRow(
                parse_run_id=r.parse_run_id,
                parser=r.parser,
                parse_config_hash=r.parse_config_hash,
                source_document_id=r.source_document_id,
                source_filename=r.source_filename,
                has_full_markdown=r.full_markdown_value is not None,
                block_count=r.block_count,
                parsed_at=r.parsed_at,
            )
            for r in rows
        ]
