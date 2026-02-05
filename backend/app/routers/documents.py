"""Documents API router."""
from uuid import UUID
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    status,
)
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.documents import get_storage_service, get_document_extractor
from app.models import User, DocumentStatus
from app.ports import StorageService, DocumentExtractor
from app.repositories.document_repository import DocumentRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUpdate,
)
from app.services.document_service import DocumentService, process_document_extraction
from app.services.exceptions import ConflictError, NotFoundError, ValidationError

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_service(
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    document_extractor: DocumentExtractor = Depends(get_document_extractor),
) -> DocumentService:
    """Dependency to create DocumentService with repositories."""
    document_repo = DocumentRepository(db)
    project_repo = ProjectRepository(db)
    return DocumentService(
        document_repo=document_repo,
        project_repo=project_repo,
        storage_service=storage_service,
        document_extractor=document_extractor,
    )


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document",
    description="Upload a document file. Returns immediately with status='processing'. "
                "Text extraction happens in the background.",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    project_id: UUID = Form(..., description="Project ID to associate document with"),
    title: str = Form(..., description="Document title"),
    description: str | None = Form(None, description="Optional document description"),
    file: bytes = File(..., description="Document file (PDF)"),
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    document_extractor: DocumentExtractor = Depends(get_document_extractor),
):
    """Upload a document and initiate background processing."""
    try:
        # Initiate upload (synchronous: validate, save, create record)
        document = await document_service.initiate_upload(
            user_id=current_user.id,
            project_id=project_id,
            file_content=file,
            filename="upload.pdf",  # File object doesn't preserve name, use generic
            title=title,
            description=description,
        )

        # Schedule background text extraction
        document_repo = DocumentRepository(db)
        background_tasks.add_task(
            process_document_extraction,
            document_id=document.id,
            document_repo=document_repo,
            storage_service=storage_service,
            document_extractor=document_extractor,
        )

        return document

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.get(
    "",
    response_model=list[DocumentListResponse],
    summary="List documents",
    description="List documents for a project with optional status filter.",
)
async def list_documents(
    project_id: UUID = Query(..., description="Project ID to list documents for"),
    status_filter: DocumentStatus | None = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """List documents for a project."""
    try:
        return await document_service.list_documents(
            project_id=project_id,
            user_id=current_user.id,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details",
    description="Get full details of a specific document including extracted text.",
)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """Get a specific document by ID."""
    try:
        return await document_service.get_document(document_id, current_user.id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get(
    "/{document_id}/file",
    summary="Download original file",
    description="Download the original uploaded file.",
    response_class=Response,
)
async def download_document_file(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """Download the original document file."""
    try:
        content, filename, mime_type = await document_service.get_file_content(
            document_id=document_id,
            user_id=current_user.id,
        )

        return Response(
            content=content,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/{document_id}/text",
    summary="Get extracted text",
    description="Get the extracted text content from the document.",
    response_model=dict,
)
async def get_document_text(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """Get extracted text content from a document."""
    try:
        text = await document_service.get_extracted_text(
            document_id=document_id,
            user_id=current_user.id,
        )
        return {"text": text}

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Update document metadata",
    description="Update document title and/or description.",
)
async def update_document(
    document_id: UUID,
    data: DocumentUpdate,
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """Update a document's metadata."""
    try:
        return await document_service.update_document(
            document_id=document_id,
            user_id=current_user.id,
            data=data,
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document",
    description="Delete a document and its associated file.",
)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """Delete a document permanently."""
    try:
        await document_service.delete_document(
            document_id=document_id,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
