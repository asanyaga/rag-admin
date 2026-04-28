"""Documents API router."""
import json
import logging
from uuid import UUID
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
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
from app.repositories.parse_run_repository import ParseRunRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.parse_result_repository import ParseResultRepository
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUpdate,
    BulkUploadItemResponse,
    BulkUploadResponse,
    BulkMoveRequest,
    BulkMoveResponse,
)
from app.schemas.parse_run import ParseRunResponse
from app.services.document_service import DocumentService, process_document_extraction, BulkUploadItemResult
from app.services.parse_service import ParseService, process_document_parsing
from app.services.exceptions import ConflictError, NotFoundError, ValidationError
from app.adapters.parsing.registry import get_parser

_CDM_PARSER_TYPES = frozenset({"llamaparse", "landing_ai"})

router = APIRouter(prefix="/documents", tags=["documents"])

logger = logging.getLogger(__name__)


def get_document_service(
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    document_extractor: DocumentExtractor = Depends(get_document_extractor),
) -> DocumentService:
    """Dependency to create DocumentService with repositories."""
    from app.config import settings
    from app.dependencies.documents import get_parsing_service
    document_repo = DocumentRepository(db)
    project_repo = ProjectRepository(db)
    parsing_service = get_parsing_service(db) if settings.USE_CDM_PARSER else None
    return DocumentService(
        document_repo=document_repo,
        project_repo=project_repo,
        storage_service=storage_service,
        document_extractor=document_extractor,
        parsing_service=parsing_service,
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
    parser_type: str = Form("simple", description="Parser type: simple or llamaparse"),
    parse_config: str | None = Form(None, description="JSON parser config (for llamaparse)"),
    folder_id: UUID | None = Form(None, description="Optional folder to place document in"),
    file: UploadFile = ...,
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    document_extractor: DocumentExtractor = Depends(get_document_extractor),
):
    """Upload a document and initiate background processing."""
    from app.config import settings
    from app.dependencies.documents import get_llamaparse_client, get_landingai_client
    from app.repositories.parse_run_repository import ParseRunRepository
    from app.repositories.parsed_document_repository import ParsedDocumentRepository
    from app.repositories.source_document_repository import SourceDocumentRepository
    from app.services.document_service import process_cdm_parsing

    try:
        config_dict = None
        if parse_config:
            try:
                config_dict = json.loads(parse_config)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON in parse_config")

        use_cdm = settings.USE_CDM_PARSER and parser_type in _CDM_PARSER_TYPES

        file_content = await file.read()
        filename = file.filename or "upload.pdf"
        document = await document_service.initiate_upload(
            user_id=current_user.id,
            project_id=project_id,
            file_content=file_content,
            filename=filename,
            title=title,
            description=description,
            folder_id=folder_id,
            use_cdm=use_cdm,
        )

        if use_cdm and document.source_document_id is not None:
            representation_kind = (config_dict or {}).get("representation_kind", "extract_rich")
            parse_cfg = {k: v for k, v in (config_dict or {}).items() if k != "representation_kind"}
            parse_cfg["parser"] = parser_type
            background_tasks.add_task(
                process_cdm_parsing,
                document_id=document.id,
                source_document_id=document.source_document_id,
                project_id=project_id,
                representation_kind=representation_kind,
                config=parse_cfg,
                document_repo=DocumentRepository(db),
                parse_run_repo=ParseRunRepository(db),
                parsed_doc_repo=ParsedDocumentRepository(db),
                source_doc_repo=SourceDocumentRepository(db),
                storage_service=storage_service,
                llamaparse_client=get_llamaparse_client(),
                landingai_client=get_landingai_client(),
            )
        else:
            if use_cdm:
                logger.warning(
                    "CDM path requested (use_cdm=True) but document.source_document_id is None "
                    "for document %s; falling back to legacy parser path",
                    document.id,
                )
            if parser_type != "simple":
                # Legacy non-CDM parser path
                parser = get_parser(parser_type)
                if parser is None:
                    raise ValidationError(f"Unknown parser type: {parser_type}")

                parse_result_repo = ParseResultRepository(db)
                document_repo_bg = DocumentRepository(db)
                parse_service = ParseService(parse_result_repo, document_repo_bg)
                parse_result = await parse_service.create_parse_result(
                    document_id=document.id,
                    user_id=current_user.id,
                    parser_type=parser_type,
                    parser_config=config_dict,
                )
                background_tasks.add_task(
                    process_document_parsing,
                    parse_result_id=parse_result.id,
                    parse_result_repo=parse_result_repo,
                    document_repo=document_repo_bg,
                    storage_service=storage_service,
                    parser=parser,
                )
            else:
                document_repo_bg = DocumentRepository(db)
                background_tasks.add_task(
                    process_document_extraction,
                    document_id=document.id,
                    document_repo=document_repo_bg,
                    storage_service=storage_service,
                    document_extractor=document_extractor,
                )

        return document

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/bulk",
    response_model=BulkUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Bulk upload documents",
    description="Upload up to 20 documents at once. Files are processed independently — "
                "a failure on one file does not block the rest. Titles are auto-set from filenames.",
)
async def bulk_upload_documents(
    background_tasks: BackgroundTasks,
    project_id: UUID = Form(..., description="Project ID to associate documents with"),
    parser_type: str = Form("simple", description="Parser type applied to all files"),
    parse_config: str | None = Form(None, description="JSON parser config (for llamaparse)"),
    files: list[UploadFile] = File(..., description="Files to upload (max 20)"),
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    document_extractor: DocumentExtractor = Depends(get_document_extractor),
):
    """Bulk upload documents and initiate background processing for each."""
    from app.config import settings
    from app.dependencies.documents import get_llamaparse_client, get_landingai_client
    from app.repositories.parse_run_repository import ParseRunRepository
    from app.repositories.parsed_document_repository import ParsedDocumentRepository
    from app.repositories.source_document_repository import SourceDocumentRepository
    from app.services.document_service import process_cdm_parsing

    if len(files) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 20 files per batch",
        )

    config_dict = None
    if parse_config:
        try:
            config_dict = json.loads(parse_config)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON in parse_config",
            )

    use_cdm = settings.USE_CDM_PARSER and parser_type in _CDM_PARSER_TYPES

    # Validate parser type upfront
    # CDM parser types bypass the legacy registry — they are handled by process_cdm_parsing.
    parser = None
    if parser_type != "simple" and parser_type not in _CDM_PARSER_TYPES:
        parser = get_parser(parser_type)
        if parser is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown parser type: {parser_type}",
            )
    # parser is used as the legacy fallback when use_cdm is False.
    # When use_cdm is True, process_cdm_parsing is dispatched instead and parser is unused.

    # Read all file contents
    file_data: list[tuple[bytes, str]] = []
    for f in files:
        content = await f.read()
        file_data.append((content, f.filename or "upload.pdf"))

    results: list[BulkUploadItemResult] = await document_service.initiate_bulk_upload(
        user_id=current_user.id,
        project_id=project_id,
        files=file_data,
        use_cdm=use_cdm,
    )

    # Register background tasks for newly created documents only
    for item in results:
        if item.document is None or not item.is_new:
            continue
        document_id = item.document.id

        if use_cdm and item.document.source_document_id is not None:
            representation_kind = (config_dict or {}).get("representation_kind", "extract_rich")
            parse_cfg = {k: v for k, v in (config_dict or {}).items() if k != "representation_kind"}
            parse_cfg["parser"] = parser_type
            background_tasks.add_task(
                process_cdm_parsing,
                document_id=document_id,
                source_document_id=item.document.source_document_id,
                project_id=project_id,
                representation_kind=representation_kind,
                config=parse_cfg,
                document_repo=DocumentRepository(db),
                parse_run_repo=ParseRunRepository(db),
                parsed_doc_repo=ParsedDocumentRepository(db),
                source_doc_repo=SourceDocumentRepository(db),
                storage_service=storage_service,
                llamaparse_client=get_llamaparse_client(),
                landingai_client=get_landingai_client(),
            )
        else:
            if use_cdm:
                logger.warning(
                    "CDM path requested (use_cdm=True) but source_document_id is None "
                    "for document %s; falling back to legacy parser path",
                    document_id,
                )
            if parser is not None:
                parse_result_repo = ParseResultRepository(db)
                document_repo_bg = DocumentRepository(db)
                parse_service = ParseService(parse_result_repo, document_repo_bg)
                parse_result = await parse_service.create_parse_result(
                    document_id=document_id,
                    user_id=current_user.id,
                    parser_type=parser_type,
                    parser_config=config_dict,
                )
                background_tasks.add_task(
                    process_document_parsing,
                    parse_result_id=parse_result.id,
                    parse_result_repo=parse_result_repo,
                    document_repo=document_repo_bg,
                    storage_service=storage_service,
                    parser=parser,
                )
            else:
                document_repo_bg = DocumentRepository(db)
                background_tasks.add_task(
                    process_document_extraction,
                    document_id=document_id,
                    document_repo=document_repo_bg,
                    storage_service=storage_service,
                    document_extractor=document_extractor,
                )

    return BulkUploadResponse(
        results=[
            BulkUploadItemResponse(
                filename=item.filename,
                document=item.document,
                error=item.error,
            )
            for item in results
        ]
    )


@router.post(
    "/bulk-move",
    response_model=BulkMoveResponse,
    summary="Bulk move documents",
    description="Move multiple documents to a folder, or unfile them (folder_id=null).",
)
async def bulk_move_documents(
    body: BulkMoveRequest,
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """Move documents to a folder or unfile them."""
    moved_count = await document_service.bulk_move(
        user_id=current_user.id,
        document_ids=body.document_ids,
        folder_id=body.folder_id,
    )
    return BulkMoveResponse(moved_count=moved_count)


@router.get(
    "",
    response_model=list[DocumentListResponse],
    summary="List documents",
    description="List documents for a project with optional status filter.",
)
async def list_documents(
    project_id: UUID = Query(..., description="Project ID to list documents for"),
    status_filter: DocumentStatus | None = Query(None, alias="status", description="Filter by status"),
    folder_id: str | None = Query(None, alias="folderId", description="Filter by folder UUID or 'none' for unfiled"),
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
            folder_id=folder_id,
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
    "/{document_id}/parse-runs",
    response_model=list[ParseRunResponse],
    summary="List CDM ParseRuns for a document",
    description=(
        "Return every CDM ParseRun associated with this document's source, "
        "newest first. Returns [] if the document has no CDM runs."
    ),
)
async def list_document_parse_runs(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List CDM ParseRuns for a document."""
    document_repo = DocumentRepository(db)
    document = await document_repo.get_by_id(document_id, current_user.id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    if document.source_document_id is None:
        return []
    runs = await ParseRunRepository(db).list_for_source_document(
        document.source_document_id
    )
    return [ParseRunResponse.from_orm_row(r) for r in runs]


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
