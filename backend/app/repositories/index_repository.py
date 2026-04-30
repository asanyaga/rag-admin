"""Repository for index data access."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Index, IndexDocument, IndexStatus, IndexDocumentStatus, Chunk, Document
from app.models.document import Document as DocumentORM
from app.models.parse_run import ParseRun
from app.schemas.index import IndexConfig


class IndexRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        project_id: UUID,
        user_id: UUID,
        name: str,
        description: str | None,
        config: IndexConfig
    ) -> Index:
        """Create a new index."""
        index = Index(
            project_id=project_id,
            created_by=user_id,
            name=name,
            description=description,
            config=config.model_dump(),
            status=IndexStatus.created
        )
        self.session.add(index)
        await self.session.commit()
        await self.session.refresh(index)
        return index

    async def get_by_id(
        self,
        index_id: UUID,
        project_id: UUID
    ) -> Index | None:
        """Get an index by ID, scoped to project."""
        result = await self.session.execute(
            select(Index).where(
                Index.id == index_id,
                Index.project_id == project_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_documents(
        self,
        index_id: UUID,
        project_id: UUID
    ) -> Index | None:
        """Get an index with its documents eagerly loaded."""
        result = await self.session.execute(
            select(Index)
            .options(selectinload(Index.index_documents).selectinload(IndexDocument.document))
            .where(
                Index.id == index_id,
                Index.project_id == project_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_name(
        self,
        project_id: UUID,
        name: str
    ) -> Index | None:
        """Get an index by name within a project."""
        result = await self.session.execute(
            select(Index).where(
                Index.project_id == project_id,
                Index.name == name
            )
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: UUID) -> list[Index]:
        """List all indexes for a project."""
        result = await self.session.execute(
            select(Index)
            .where(Index.project_id == project_id)
            .order_by(Index.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(
        self,
        index_id: UUID,
        project_id: UUID,
        name: str | None = None,
        description: str | None = None
    ) -> Index | None:
        """Update an index's name and/or description.

        Note: Only allowed when status is 'created'.
        """
        index = await self.get_by_id(index_id, project_id)
        if not index:
            return None

        if name is not None:
            index.name = name
        if description is not None:
            index.description = description

        await self.session.commit()
        await self.session.refresh(index)
        return index

    async def update_status(
        self,
        index_id: UUID,
        status: IndexStatus,
        error_message: str | None = None
    ) -> Index | None:
        """Update an index's status."""
        result = await self.session.execute(
            select(Index).where(Index.id == index_id)
        )
        index = result.scalar_one_or_none()
        if not index:
            return None

        index.status = status
        index.error_message = error_message
        await self.session.commit()
        await self.session.refresh(index)
        return index

    async def update_stats(
        self,
        index_id: UUID,
        stats: dict
    ) -> Index | None:
        """Update an index's stats."""
        result = await self.session.execute(
            select(Index).where(Index.id == index_id)
        )
        index = result.scalar_one_or_none()
        if not index:
            return None

        index.stats = stats
        await self.session.commit()
        await self.session.refresh(index)
        return index

    async def delete(self, index_id: UUID, project_id: UUID) -> bool:
        """Delete an index. Returns True if deleted."""
        result = await self.session.execute(
            delete(Index).where(
                Index.id == index_id,
                Index.project_id == project_id
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    # Index-Document relationship methods

    async def add_parsed_documents(
        self,
        index_id: UUID,
        parsed_document_ids: list[UUID],
    ) -> list[IndexDocument]:
        """Add parsed-documents to an index.

        Each `parsed_document_id` is the parse_run_id of a ParsedDocument
        (under the current 1:1 schema). The corresponding `document_id` is
        looked up via the parsed-doc → source_document → document chain.
        """
        if not parsed_document_ids:
            return []

        # Resolve (parse_run_id, source_document_id) pairs.
        pr_rows = await self.session.execute(
            select(ParseRun.id, ParseRun.source_document_id)
            .where(ParseRun.id.in_(parsed_document_ids))
        )
        sd_by_pr = {pr_id: sd_id for pr_id, sd_id in pr_rows.all()}

        # Resolve source_document_id -> document_id (any Document referencing it).
        src_ids = list(sd_by_pr.values())
        doc_rows = await self.session.execute(
            select(DocumentORM.id, DocumentORM.source_document_id)
            .where(DocumentORM.source_document_id.in_(src_ids))
        )
        doc_by_sd: dict[UUID, UUID] = {}
        # Multiple Documents can share a source_document (deduplicated content);
        # take whichever appears first.
        for doc_id, sd_id in doc_rows.all():
            doc_by_sd.setdefault(sd_id, doc_id)

        rows: list[IndexDocument] = []
        for parsed_doc_id in parsed_document_ids:
            sd_id = sd_by_pr.get(parsed_doc_id)
            if sd_id is None:
                raise ValueError(f"Parsed document {parsed_doc_id} not found")
            doc_id = doc_by_sd.get(sd_id)
            if doc_id is None:
                raise ValueError(
                    f"No Document references source_document {sd_id} "
                    f"for parsed_document {parsed_doc_id}"
                )
            row = IndexDocument(
                index_id=index_id,
                document_id=doc_id,
                parse_run_id=parsed_doc_id,
                processing_status=IndexDocumentStatus.pending,
            )
            self.session.add(row)
            rows.append(row)

        await self.session.commit()
        for row in rows:
            await self.session.refresh(row)
        return rows

    async def remove_document(
        self,
        index_id: UUID,
        document_id: UUID
    ) -> bool:
        """Remove a document from an index."""
        result = await self.session.execute(
            delete(IndexDocument).where(
                IndexDocument.index_id == index_id,
                IndexDocument.document_id == document_id
            )
        )
        # Also delete associated chunks
        await self.session.execute(
            delete(Chunk).where(
                Chunk.index_id == index_id,
                Chunk.document_id == document_id
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def get_index_documents(
        self,
        index_id: UUID
    ) -> list[IndexDocument]:
        """Get all index-document associations for an index."""
        result = await self.session.execute(
            select(IndexDocument)
            .options(selectinload(IndexDocument.document))
            .where(IndexDocument.index_id == index_id)
        )
        return list(result.scalars().all())

    async def update_document_status(
        self,
        index_id: UUID,
        document_id: UUID,
        status: IndexDocumentStatus,
        error_message: str | None = None,
        chunks_created: int | None = None
    ) -> IndexDocument | None:
        """Update a document's processing status within an index."""
        result = await self.session.execute(
            select(IndexDocument).where(
                IndexDocument.index_id == index_id,
                IndexDocument.document_id == document_id
            )
        )
        index_doc = result.scalar_one_or_none()
        if not index_doc:
            return None

        index_doc.processing_status = status
        index_doc.error_message = error_message
        if status == IndexDocumentStatus.completed:
            index_doc.processed_at = datetime.utcnow()
            index_doc.chunks_created = chunks_created
        elif status == IndexDocumentStatus.failed:
            index_doc.processed_at = datetime.utcnow()

        await self.session.commit()
        await self.session.refresh(index_doc)
        return index_doc

    async def get_pending_documents(
        self,
        index_id: UUID
    ) -> list[IndexDocument]:
        """Get all pending documents for processing."""
        result = await self.session.execute(
            select(IndexDocument)
            .options(selectinload(IndexDocument.document))
            .where(
                IndexDocument.index_id == index_id,
                IndexDocument.processing_status == IndexDocumentStatus.pending
            )
        )
        return list(result.scalars().all())

    # Count methods

    async def get_document_ids(self, index_id: UUID) -> list[UUID]:
        """Get all document IDs associated with an index."""
        result = await self.session.execute(
            select(IndexDocument.document_id)
            .where(IndexDocument.index_id == index_id)
        )
        return list(result.scalars().all())

    async def count_documents(self, index_id: UUID) -> int:
        """Count documents in an index."""
        result = await self.session.execute(
            select(func.count())
            .select_from(IndexDocument)
            .where(IndexDocument.index_id == index_id)
        )
        return result.scalar() or 0

    async def count_chunks(self, index_id: UUID) -> int:
        """Count chunks in an index."""
        result = await self.session.execute(
            select(func.count())
            .select_from(Chunk)
            .where(Chunk.index_id == index_id)
        )
        return result.scalar() or 0

    async def get_processing_stats(self, index_id: UUID) -> dict:
        """Get processing statistics for an index."""
        # Total documents
        total = await self.session.execute(
            select(func.count())
            .select_from(IndexDocument)
            .where(IndexDocument.index_id == index_id)
        )
        total_docs = total.scalar() or 0

        # Completed documents
        completed = await self.session.execute(
            select(func.count())
            .select_from(IndexDocument)
            .where(
                IndexDocument.index_id == index_id,
                IndexDocument.processing_status == IndexDocumentStatus.completed
            )
        )
        completed_docs = completed.scalar() or 0

        # Failed documents
        failed = await self.session.execute(
            select(func.count())
            .select_from(IndexDocument)
            .where(
                IndexDocument.index_id == index_id,
                IndexDocument.processing_status == IndexDocumentStatus.failed
            )
        )
        failed_docs = failed.scalar() or 0

        return {
            "total": total_docs,
            "completed": completed_docs,
            "failed": failed_docs,
            "pending": total_docs - completed_docs - failed_docs
        }

    # CDM versioning and event methods

    async def increment_version(self, index_id: UUID) -> None:
        """Increment the version counter on an index."""
        result = await self.session.execute(
            select(Index).where(Index.id == index_id)
        )
        index = result.scalar_one_or_none()
        if index:
            index.version += 1
            await self.session.commit()

    async def write_index_event(
        self,
        index_id: UUID,
        version: int,
        config_snapshot: dict,
        document_bindings: dict,
        triggered_by: UUID,
    ) -> "IndexEvent":
        """Write an immutable audit event recording the index state at trigger time."""
        from app.models.index_event import IndexEvent
        event = IndexEvent(
            index_id=index_id,
            version=version,
            config_snapshot=config_snapshot,
            document_bindings=document_bindings,
            triggered_by=triggered_by,
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event
