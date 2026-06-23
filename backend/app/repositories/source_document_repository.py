"""Repository for SourceDocument — content-addressed bytes layer."""
from uuid import UUID

from sqlalchemy import func, distinct, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.source_document import SourceDocument


class SourceDocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        sha256: str,
        storage_uri: str,
        filename: str | None = None,
        mime_type: str | None = None,
        byte_size: int | None = None,
    ) -> SourceDocument:
        row = SourceDocument(
            sha256=sha256,
            storage_uri=storage_uri,
            filename=filename,
            mime_type=mime_type,
            byte_size=byte_size,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get(self, source_document_id: UUID) -> SourceDocument | None:
        result = await self.session.execute(
            select(SourceDocument).where(SourceDocument.id == source_document_id)
        )
        return result.scalar_one_or_none()

    async def get_by_sha256(self, sha256: str) -> SourceDocument | None:
        result = await self.session.execute(
            select(SourceDocument).where(SourceDocument.sha256 == sha256)
        )
        return result.scalar_one_or_none()

    async def update_storage_uri(self, source_document_id: UUID, storage_uri: str) -> None:
        result = await self.session.execute(
            select(SourceDocument).where(SourceDocument.id == source_document_id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            row.storage_uri = storage_uri
            await self.session.commit()

    async def list_all(self) -> list[tuple[SourceDocument, int]]:
        """Return all source documents with the number of distinct projects referencing each."""
        stmt = (
            select(
                SourceDocument,
                func.count(distinct(Document.project_id)).label("project_count"),
            )
            .outerjoin(Document, Document.source_document_id == SourceDocument.id)
            .group_by(SourceDocument.id)
            .order_by(SourceDocument.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return [(row.SourceDocument, row.project_count) for row in result]

    async def get_or_create_by_sha256(
        self,
        *,
        sha256: str,
        storage_uri: str,
        filename: str | None = None,
        mime_type: str | None = None,
        byte_size: int | None = None,
    ) -> tuple[SourceDocument, bool]:
        existing = await self.get_by_sha256(sha256)
        if existing is not None:
            return existing, False
        try:
            created = await self.create(
                sha256=sha256, storage_uri=storage_uri,
                filename=filename, mime_type=mime_type, byte_size=byte_size,
            )
            return created, True
        except IntegrityError:
            # Lost the race. Roll back and re-read.
            await self.session.rollback()
            existing = await self.get_by_sha256(sha256)
            assert existing is not None, "IntegrityError but sha256 not found"
            return existing, False
