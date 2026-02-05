from uuid import UUID
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, Project, DocumentStatus
from app.schemas.document import DocumentUpdate


class DocumentRepository:
    """Repository for document data access with user access control."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        project_id: UUID,
        user_id: UUID,
        source_type: str,
        source_identifier: str,
        title: str,
        description: str | None,
        source_metadata: dict,
    ) -> Document:
        """Create a new document.

        Args:
            project_id: Project UUID
            user_id: User UUID (for created_by)
            source_type: Source type (e.g., "upload")
            source_identifier: Source identifier (e.g., checksum)
            title: Document title
            description: Optional description
            source_metadata: Source-specific metadata

        Returns:
            Created document
        """
        document = Document(
            project_id=project_id,
            created_by=user_id,
            source_type=source_type,
            source_identifier=source_identifier,
            title=title,
            description=description,
            source_metadata=source_metadata,
            status=DocumentStatus.processing,
        )
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def get_by_id(self, document_id: UUID, user_id: UUID) -> Document | None:
        """Get a document by ID, scoped to user via project ownership.

        Args:
            document_id: Document UUID
            user_id: User UUID

        Returns:
            Document if found and user has access, None otherwise
        """
        result = await self.session.execute(
            select(Document)
            .join(Document.project)
            .where(
                and_(
                    Document.id == document_id,
                    Project.user_id == user_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_source(
        self,
        project_id: UUID,
        user_id: UUID,
        source_type: str,
        source_identifier: str
    ) -> Document | None:
        """Get a document by source (for duplicate detection).

        Args:
            project_id: Project UUID
            user_id: User UUID
            source_type: Source type
            source_identifier: Source identifier (e.g., checksum)

        Returns:
            Document if found, None otherwise
        """
        result = await self.session.execute(
            select(Document)
            .join(Document.project)
            .where(
                and_(
                    Document.project_id == project_id,
                    Document.source_type == source_type,
                    Document.source_identifier == source_identifier,
                    Project.user_id == user_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_by_project(
        self,
        project_id: UUID,
        user_id: UUID,
        status: DocumentStatus | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[Document]:
        """List documents for a project, scoped to user.

        Args:
            project_id: Project UUID
            user_id: User UUID
            status: Optional status filter
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of documents
        """
        query = (
            select(Document)
            .join(Document.project)
            .where(
                and_(
                    Document.project_id == project_id,
                    Project.user_id == user_id
                )
            )
        )

        if status:
            query = query.where(Document.status == status)

        query = query.order_by(Document.created_at.desc()).limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        document_id: UUID,
        user_id: UUID,
        data: DocumentUpdate
    ) -> Document | None:
        """Update a document's metadata, scoped to user.

        Args:
            document_id: Document UUID
            user_id: User UUID
            data: Update data

        Returns:
            Updated document if found, None otherwise
        """
        document = await self.get_by_id(document_id, user_id)
        if not document:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(document, key, value)

        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def update_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
        status_message: str | None = None
    ) -> Document | None:
        """Update document processing status (no user scoping for background tasks).

        Args:
            document_id: Document UUID
            status: New status
            status_message: Optional status message

        Returns:
            Updated document if found, None otherwise
        """
        result = await self.session.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            return None

        document.status = status
        document.status_message = status_message

        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def update_extraction(
        self,
        document_id: UUID,
        extracted_text: str,
        processing_metadata: dict,
        status: DocumentStatus = DocumentStatus.ready
    ) -> Document | None:
        """Update document with extraction results (no user scoping for background tasks).

        Args:
            document_id: Document UUID
            extracted_text: Extracted text content
            processing_metadata: Processing metadata
            status: New status (default: READY)

        Returns:
            Updated document if found, None otherwise
        """
        result = await self.session.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            return None

        document.extracted_text = extracted_text
        document.processing_metadata = processing_metadata
        document.status = status
        document.status_message = None  # Clear any error message

        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def delete(self, document_id: UUID, user_id: UUID) -> bool:
        """Delete a document, scoped to user.

        Args:
            document_id: Document UUID
            user_id: User UUID

        Returns:
            True if deleted, False if not found
        """
        document = await self.get_by_id(document_id, user_id)
        if not document:
            return False

        await self.session.delete(document)
        await self.session.commit()
        return True
