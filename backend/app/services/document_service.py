"""Document service with business logic."""
from uuid import UUID
from pathlib import Path
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.models import DocumentStatus
from app.ports import DocumentExtractor, StorageService
from app.repositories.document_repository import DocumentRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUpdate,
)
from app.services.exceptions import ConflictError, NotFoundError, ValidationError
from app.utils.file_validation import (
    FileValidationError,
    validate_file_size,
    validate_mime_type,
    compute_checksum,
)


class DocumentService:
    """Service for document operations."""

    def __init__(
        self,
        document_repo: DocumentRepository,
        project_repo: ProjectRepository,
        storage_service: StorageService,
        document_extractor: DocumentExtractor,
    ):
        self.document_repo = document_repo
        self.project_repo = project_repo
        self.storage_service = storage_service
        self.document_extractor = document_extractor

    async def initiate_upload(
        self,
        user_id: UUID,
        project_id: UUID,
        file_content: bytes,
        filename: str,
        title: str,
        description: str | None = None,
    ) -> DocumentResponse:
        """Initiate document upload (validate, save file, create record).

        This method performs synchronous operations and returns immediately.
        Background text extraction should be triggered separately.

        Args:
            user_id: User UUID
            project_id: Project UUID
            file_content: File content as bytes
            filename: Original filename
            title: Document title
            description: Optional description

        Returns:
            Created document with status='processing'

        Raises:
            NotFoundError: Project not found or user doesn't have access
            ValidationError: File validation failed
            ConflictError: Document with same content already exists
        """
        # 1. Verify project exists and user has access
        project = await self.project_repo.get_by_id(project_id, user_id)
        if not project:
            raise NotFoundError(f"Project {project_id} not found")

        # 2. Validate file size
        try:
            validate_file_size(
                file_size=len(file_content),
                max_size_mb=settings.MAX_UPLOAD_SIZE_MB
            )
        except FileValidationError as e:
            raise ValidationError(str(e))

        # 3. Validate MIME type
        try:
            mime_type = validate_mime_type(
                file_content=file_content,
                filename=filename,
                allowed_types=settings.ALLOWED_MIME_TYPES
            )
        except FileValidationError as e:
            raise ValidationError(str(e))

        # 4. Compute checksum for duplicate detection
        checksum = compute_checksum(file_content)

        # 5. Check for duplicate document
        existing = await self.document_repo.get_by_source(
            project_id=project_id,
            user_id=user_id,
            source_type="upload",
            source_identifier=checksum
        )
        if existing:
            raise ConflictError(
                f"Document with same content already exists: {existing.title}"
            )

        # 6. Save file to storage
        file_extension = Path(filename).suffix.lower()
        relative_path = f"projects/{project_id}/uploads/{checksum}{file_extension}"

        try:
            file_path = await self.storage_service.save(file_content, relative_path)
        except Exception as e:
            raise ValidationError(f"Failed to save file: {e}")

        # 7. Create document record
        source_metadata = {
            "filename": filename,
            "file_path": file_path,
            "file_size": len(file_content),
            "mime_type": mime_type,
            "checksum": checksum,
        }

        try:
            document = await self.document_repo.create(
                project_id=project_id,
                user_id=user_id,
                source_type="upload",
                source_identifier=checksum,
                title=title,
                description=description,
                source_metadata=source_metadata,
            )
        except IntegrityError as e:
            # Clean up file if database insert fails
            try:
                await self.storage_service.delete(file_path)
            except Exception:
                pass  # Log but don't raise

            error_str = str(e).lower()
            if 'uq_documents_project_source' in error_str:
                raise ConflictError("Document with same content already exists")
            raise

        return DocumentResponse.model_validate(document)

    async def get_document(
        self,
        document_id: UUID,
        user_id: UUID
    ) -> DocumentResponse:
        """Get a document by ID.

        Args:
            document_id: Document UUID
            user_id: User UUID

        Returns:
            Document response

        Raises:
            NotFoundError: Document not found or user doesn't have access
        """
        document = await self.document_repo.get_by_id(document_id, user_id)
        if not document:
            raise NotFoundError(f"Document {document_id} not found")
        return DocumentResponse.model_validate(document)

    async def list_documents(
        self,
        project_id: UUID,
        user_id: UUID,
        status: DocumentStatus | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[DocumentListResponse]:
        """List documents for a project.

        Args:
            project_id: Project UUID
            user_id: User UUID
            status: Optional status filter
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of documents

        Raises:
            NotFoundError: Project not found or user doesn't have access
        """
        # Verify project exists and user has access
        project = await self.project_repo.get_by_id(project_id, user_id)
        if not project:
            raise NotFoundError(f"Project {project_id} not found")

        documents = await self.document_repo.list_by_project(
            project_id=project_id,
            user_id=user_id,
            status=status,
            limit=limit,
            offset=offset
        )
        return [DocumentListResponse.model_validate(d) for d in documents]

    async def update_document(
        self,
        document_id: UUID,
        user_id: UUID,
        data: DocumentUpdate
    ) -> DocumentResponse:
        """Update a document's metadata.

        Args:
            document_id: Document UUID
            user_id: User UUID
            data: Update data

        Returns:
            Updated document

        Raises:
            NotFoundError: Document not found or user doesn't have access
        """
        document = await self.document_repo.update(document_id, user_id, data)
        if not document:
            raise NotFoundError(f"Document {document_id} not found")
        return DocumentResponse.model_validate(document)

    async def delete_document(
        self,
        document_id: UUID,
        user_id: UUID
    ) -> None:
        """Delete a document and its associated file.

        Args:
            document_id: Document UUID
            user_id: User UUID

        Raises:
            NotFoundError: Document not found or user doesn't have access
        """
        # Get document first to access file path
        document = await self.document_repo.get_by_id(document_id, user_id)
        if not document:
            raise NotFoundError(f"Document {document_id} not found")

        # Delete file from storage (best effort)
        if document.source_metadata.get("file_path"):
            try:
                await self.storage_service.delete(
                    document.source_metadata["file_path"]
                )
            except Exception:
                pass  # Log but don't raise - proceed with database deletion

        # Delete database record
        deleted = await self.document_repo.delete(document_id, user_id)
        if not deleted:
            raise NotFoundError(f"Document {document_id} not found")

    async def get_file_content(
        self,
        document_id: UUID,
        user_id: UUID
    ) -> tuple[bytes, str, str]:
        """Get the original file content for download.

        Args:
            document_id: Document UUID
            user_id: User UUID

        Returns:
            Tuple of (file_content, filename, mime_type)

        Raises:
            NotFoundError: Document or file not found
        """
        document = await self.document_repo.get_by_id(document_id, user_id)
        if not document:
            raise NotFoundError(f"Document {document_id} not found")

        file_path = document.source_metadata.get("file_path")
        if not file_path:
            raise NotFoundError("File path not found in document metadata")

        try:
            content = await self.storage_service.get(file_path)
        except FileNotFoundError:
            raise NotFoundError(f"File not found: {file_path}")
        except Exception as e:
            raise ValidationError(f"Failed to retrieve file: {e}")

        filename = document.source_metadata.get("filename", "document")
        mime_type = document.source_metadata.get("mime_type", "application/octet-stream")

        return content, filename, mime_type

    async def get_extracted_text(
        self,
        document_id: UUID,
        user_id: UUID
    ) -> str:
        """Get the extracted text content.

        Args:
            document_id: Document UUID
            user_id: User UUID

        Returns:
            Extracted text content

        Raises:
            NotFoundError: Document not found or text not extracted yet
            ValidationError: Document processing failed
        """
        document = await self.document_repo.get_by_id(document_id, user_id)
        if not document:
            raise NotFoundError(f"Document {document_id} not found")

        if document.status == DocumentStatus.processing:
            raise ValidationError("Document is still being processed")

        if document.status == DocumentStatus.failed:
            raise ValidationError(
                f"Document processing failed: {document.status_message or 'Unknown error'}"
            )

        if not document.extracted_text:
            raise NotFoundError("Extracted text not available")

        return document.extracted_text


async def process_document_extraction(
    document_id: UUID,
    document_repo: DocumentRepository,
    storage_service: StorageService,
    document_extractor: DocumentExtractor,
) -> None:
    """Background task to extract text from a document.

    This function is designed to be called from FastAPI BackgroundTasks.

    Args:
        document_id: Document UUID
        document_repo: Document repository instance
        storage_service: Storage service instance
        document_extractor: Document extractor instance
    """
    try:
        # Get document (no user scoping for background task)
        from sqlalchemy import select
        from app.models import Document

        result = await document_repo.session.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            return  # Document deleted before processing

        # Get file path and MIME type
        file_path = document.source_metadata.get("file_path")
        mime_type = document.source_metadata.get("mime_type")

        if not file_path or not mime_type:
            await document_repo.update_status(
                document_id=document_id,
                status=DocumentStatus.failed,
                status_message="Missing file path or MIME type"
            )
            return

        # Extract text
        extraction_result = await document_extractor.extract(file_path, mime_type)

        # Update source_metadata with page_count
        document.source_metadata["page_count"] = extraction_result.page_count

        # Update document with extraction results
        await document_repo.update_extraction(
            document_id=document_id,
            extracted_text=extraction_result.text,
            processing_metadata=extraction_result.metadata,
            status=DocumentStatus.ready
        )

    except Exception as e:
        # Update status to failed
        await document_repo.update_status(
            document_id=document_id,
            status=DocumentStatus.failed,
            status_message=str(e)
        )
