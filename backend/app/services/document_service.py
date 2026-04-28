"""Document service with business logic."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID
from pathlib import Path
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.services.parsing.parsing_service import ParsingService

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


@dataclass
class BulkUploadItemResult:
    """Result for a single file in a bulk upload."""
    filename: str
    document: "DocumentResponse | None" = None
    error: str | None = None
    is_new: bool = True


class DocumentService:
    """Service for document operations."""

    def __init__(
        self,
        document_repo: DocumentRepository,
        project_repo: ProjectRepository,
        storage_service: StorageService,
        document_extractor: DocumentExtractor,
        parsing_service: ParsingService | None = None,
    ):
        self.document_repo = document_repo
        self.project_repo = project_repo
        self.storage_service = storage_service
        self.document_extractor = document_extractor
        self.parsing_service = parsing_service

    async def initiate_upload(
        self,
        user_id: UUID,
        project_id: UUID,
        file_content: bytes,
        filename: str,
        title: str,
        description: str | None = None,
        folder_id: UUID | None = None,
        use_cdm: bool = False,
    ) -> DocumentResponse:
        """Initiate document upload (validate, save file, create record).

        When use_cdm=True and parsing_service is set, calls
        ParsingService.ensure_source_document and creates the Document with
        source_document_id populated. Parsing is dispatched as a background task
        by the caller (see process_cdm_parsing).

        When use_cdm=False (or parsing_service is None), falls back to the legacy
        storage + extraction path.

        Returns immediately with status='processing'. Background parsing/extraction
        is triggered separately by the router.
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

        if use_cdm and self.parsing_service is not None:
            # CDM path: ensure_source_document handles storage + source dedup
            source_doc = await self.parsing_service.ensure_source_document(
                bytes_=file_content,
                filename=filename,
                mime_type=mime_type,
            )
            source_metadata = {
                "filename": filename,
                "file_path": source_doc.storage_uri,
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
                    folder_id=folder_id,
                    source_document_id=UUID(source_doc.id),
                )
            except IntegrityError as e:
                error_str = str(e).lower()
                if 'uq_documents_project_source' in error_str:
                    raise ConflictError("Document with same content already exists")
                raise
        else:
            if use_cdm and self.parsing_service is None:
                logger.warning(
                    "use_cdm=True but parsing_service is None; falling back to legacy path for document upload"
                )
            # Legacy path (unchanged from original)
            file_extension = Path(filename).suffix.lower()
            relative_path = f"projects/{project_id}/uploads/{checksum}{file_extension}"

            try:
                file_path = await self.storage_service.save(file_content, relative_path)
            except Exception as e:
                raise ValidationError(f"Failed to save file: {e}")

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
                    folder_id=folder_id,
                )
            except IntegrityError as e:
                # Clean up file if database insert fails
                try:
                    await self.storage_service.delete(file_path)
                except Exception:
                    pass
                error_str = str(e).lower()
                if 'uq_documents_project_source' in error_str:
                    raise ConflictError("Document with same content already exists")
                raise

        return DocumentResponse.model_validate(document)

    async def initiate_bulk_upload(
        self,
        user_id: UUID,
        project_id: UUID,
        files: list[tuple[bytes, str]],
        use_cdm: bool = False,
    ) -> list[BulkUploadItemResult]:
        """Initiate upload for multiple files. Each file is processed independently.

        Args:
            user_id: User UUID
            project_id: Project UUID
            files: List of (file_content, filename) tuples

        Returns:
            List of BulkUploadItemResult — one per file, with document or error set.
            Duplicates are returned as the existing document with is_new=False.
        """
        results: list[BulkUploadItemResult] = []
        for file_content, filename in files:
            title = Path(filename).stem
            try:
                document = await self.initiate_upload(
                    user_id=user_id,
                    project_id=project_id,
                    file_content=file_content,
                    filename=filename,
                    title=title,
                    use_cdm=use_cdm,
                )
                results.append(BulkUploadItemResult(filename=filename, document=document, is_new=True))
            except ConflictError:
                checksum = compute_checksum(file_content)
                existing = await self.document_repo.get_by_source(
                    project_id=project_id,
                    user_id=user_id,
                    source_type="upload",
                    source_identifier=checksum,
                )
                doc_response = DocumentResponse.model_validate(existing) if existing else None
                results.append(BulkUploadItemResult(filename=filename, document=doc_response, is_new=False))
            except (ValidationError, NotFoundError) as e:
                results.append(BulkUploadItemResult(filename=filename, error=str(e)))
        return results

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

    async def bulk_move(
        self,
        user_id: UUID,
        document_ids: list[UUID],
        folder_id: "UUID | None",
    ) -> int:
        """Move documents to a folder (or unfile). Returns count of moved documents."""
        return await self.document_repo.bulk_move(document_ids, user_id, folder_id)

    async def list_documents(
        self,
        project_id: UUID,
        user_id: UUID,
        status: DocumentStatus | None = None,
        folder_id: "str | None" = None,
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
            folder_id=folder_id,
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

        # Store page boundaries in processing metadata for chunking
        extraction_result.metadata["page_boundaries"] = extraction_result.page_boundaries

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


async def process_cdm_parsing(
    document_id: UUID,
    source_document_id: UUID,
    project_id: UUID,
    representation_kind: str,
    config: dict,
    document_repo: DocumentRepository,
    parse_run_repo: Any,
    parsed_doc_repo: Any,
    source_doc_repo: Any,
    storage_service: StorageService,
    llamaparse_client: Any,
    landingai_client: Any = None,
    simple_client: Any = None,
) -> None:
    """Background task: CDM parse + persist for a newly uploaded document.

    Creates a ParsingService from the provided repos and client, runs
    parse_and_persist, and writes the extracted_text shim for downstream readers.
    """
    from app.cdm.models import ParserKind
    from app.cdm.source import SourceDocument as SourceDocumentCDM
    from app.services.parsing.errors import ParseFailedError
    from app.services.parsing.parsing_service import ParsingService

    # Fetch source document ORM
    source_orm = await source_doc_repo.get(source_document_id)
    if source_orm is None:
        await document_repo.update_status(
            document_id=document_id,
            status=DocumentStatus.failed,
            status_message="SourceDocument not found",
        )
        return

    # Fetch Document to get file_path
    doc = await document_repo.get_by_id_unscoped(document_id)
    if doc is None:
        return  # Deleted before task ran

    file_path = doc.source_metadata.get("file_path")
    if not file_path:
        await document_repo.update_status(
            document_id=document_id,
            status=DocumentStatus.failed,
            status_message="Missing file_path in source_metadata",
        )
        return

    source_cdm = SourceDocumentCDM(
        id=str(source_orm.id),
        sha256=source_orm.sha256,
        filename=source_orm.filename,
        mime_type=source_orm.mime_type,
        byte_size=source_orm.byte_size,
        storage_uri=source_orm.storage_uri,
        created_at=source_orm.created_at,
    )

    from app.dependencies.documents import get_document_extractor
    service = ParsingService(
        source_doc_repo=source_doc_repo,
        parse_run_repo=parse_run_repo,
        parsed_doc_repo=parsed_doc_repo,
        storage=storage_service,
        clients={
            ParserKind.LLAMAPARSE: llamaparse_client,
            ParserKind.LANDING_AI: landingai_client,
            ParserKind.SIMPLE: simple_client if simple_client is not None else get_document_extractor(),
        },
    )

    try:
        run, parsed_doc = await service.parse_and_persist(
            source=source_cdm,
            file_path=file_path,
            representation_kind=representation_kind,
            config=config,
            project_id=project_id,
        )
    except ParseFailedError as e:
        await document_repo.update_status(
            document_id=document_id,
            status=DocumentStatus.failed,
            status_message=str(e),
        )
        return

    if parsed_doc is not None:
        # extracted_text shim: keeps downstream readers working until migration spec retires it
        await document_repo.update_extraction(
            document_id=document_id,
            extracted_text=parsed_doc.full_text or "",
            processing_metadata={},
            status=DocumentStatus.ready,
        )
    else:
        await document_repo.update_status(
            document_id=document_id,
            status=DocumentStatus.failed,
            status_message=f"Parse run finished with status: {run.status.value}",
        )
