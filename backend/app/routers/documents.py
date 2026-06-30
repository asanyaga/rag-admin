"""Documents API router."""
import json
import logging
import os
import tempfile
from pathlib import Path
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
from app.dependencies.documents import get_storage_service
from app.models import User, DocumentStatus
from app.ports import StorageService
from app.repositories.document_repository import DocumentRepository
from app.repositories.parse_run_repository import ParseRunRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.provider_key_repository import ProviderKeyRepository
from app.services.provider_key_service import resolve_api_key
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUpdate,
    BulkUploadItemResponse,
    BulkUploadResponse,
    BulkMoveRequest,
    BulkMoveResponse,
    DocumentFromSourceRequest,
)
from app.repositories.source_document_repository import SourceDocumentRepository
from app.schemas.parse_run import ParseRunResponse
from app.services.document_service import DocumentService, process_cdm_parsing, BulkUploadItemResult
from app.services.exceptions import ConflictError, NotFoundError, ValidationError
from app.cdm.adapters.local_pipeline.probe import DocumentProbe
from pydantic import BaseModel as PydanticBaseModel


class _ParseRunCreateRequest(PydanticBaseModel):
    parser_type: str = "simple"
    config: dict | None = None


_PARSER_PROVIDER: dict[str, str] = {
    "llamaparse": "llama_cloud",
    "landing_ai": "landing_ai",
}

_PARSER_KEY_LABEL: dict[str, str] = {
    "llamaparse": "LlamaCloud",
    "landing_ai": "Landing AI",
}


async def _resolve_parser_key(
    db: AsyncSession,
    user_id: UUID,
    parser_type: str,
) -> tuple[str | None, str | None]:
    """Return (llamaparse_api_key, landingai_api_key) for the given parser type.

    Raises HTTP 400 if the chosen parser requires a key that is not configured
    in BYOK settings or the environment.
    """
    provider = _PARSER_PROVIDER.get(parser_type)
    if not provider:
        return None, None  # simple parser — no key needed

    key = await resolve_api_key(ProviderKeyRepository(db), user_id, provider)
    if not key:
        label = _PARSER_KEY_LABEL.get(parser_type, parser_type)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No {label} API key configured. Add one in Settings → API Keys.",
        )

    if parser_type == "llamaparse":
        return key, None
    return None, key

router = APIRouter(prefix="/documents", tags=["documents"])

logger = logging.getLogger(__name__)


def get_document_service(
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
) -> DocumentService:
    from app.dependencies.documents import get_parsing_service
    document_repo = DocumentRepository(db)
    project_repo = ProjectRepository(db)
    parsing_service = get_parsing_service(db)
    return DocumentService(
        document_repo=document_repo,
        project_repo=project_repo,
        storage_service=storage_service,
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
    parser_type: str = Form("simple", description="Parser type: simple, llamaparse, or landing_ai"),
    parse_config: str | None = Form(None, description="JSON parser config (for llamaparse or landing_ai)"),
    folder_id: UUID | None = Form(None, description="Optional folder to place document in"),
    file: UploadFile = ...,
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
):
    """Upload a document and initiate background processing."""
    llamaparse_api_key, landingai_api_key = await _resolve_parser_key(
        db, current_user.id, parser_type
    )

    try:
        config_dict = None
        if parse_config:
            try:
                config_dict = json.loads(parse_config)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON in parse_config")

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
            use_cdm=True,
        )

        if document.source_document_id is not None:
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
                storage_service=storage_service,
                llamaparse_api_key=llamaparse_api_key,
                landingai_api_key=landingai_api_key,
            )
        else:
            logger.error(
                "document.source_document_id is None after CDM upload for document %s",
                document.id,
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
    parse_config: str | None = Form(None, description="JSON parser config (for llamaparse or landing_ai)"),
    files: list[UploadFile] = File(..., description="Files to upload (max 20)"),
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
):
    """Bulk upload documents and initiate background processing for each."""
    llamaparse_api_key, landingai_api_key = await _resolve_parser_key(
        db, current_user.id, parser_type
    )

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

    # Read all file contents
    file_data: list[tuple[bytes, str]] = []
    for f in files:
        content = await f.read()
        file_data.append((content, f.filename or "upload.pdf"))

    results: list[BulkUploadItemResult] = await document_service.initiate_bulk_upload(
        user_id=current_user.id,
        project_id=project_id,
        files=file_data,
        use_cdm=True,
    )

    # Register background tasks for newly created documents only
    for item in results:
        if item.document is None or not item.is_new:
            continue
        document_id = item.document.id

        if item.document.source_document_id is not None:
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
                storage_service=storage_service,
                llamaparse_api_key=llamaparse_api_key,
                landingai_api_key=landingai_api_key,
            )
        else:
            logger.error(
                "source_document_id is None after CDM upload for document %s",
                document_id,
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


@router.post(
    "/from-source",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Add a source document to a project and parse it",
    description="Links an existing source document into a project without re-uploading "
                "the file, then kicks off a background parse run.",
)
async def add_document_from_source(
    body: DocumentFromSourceRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
):
    """Link source document to project and initiate parsing."""
    llamaparse_api_key, landingai_api_key = await _resolve_parser_key(
        db, current_user.id, body.parser_type
    )

    source_doc_repo = SourceDocumentRepository(db)
    source_doc = await source_doc_repo.get(body.source_document_id)
    if source_doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source document not found",
        )

    try:
        document = await document_service.add_from_source(
            user_id=current_user.id,
            project_id=body.project_id,
            source_document_id=body.source_document_id,
            source_doc_filename=source_doc.filename,
            source_doc_storage_uri=source_doc.storage_uri,
            source_doc_sha256=source_doc.sha256,
            source_doc_byte_size=source_doc.byte_size,
            source_doc_mime_type=source_doc.mime_type,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    if document.source_document_id is not None:
        config = dict(body.parse_config or {})
        representation_kind = config.pop("representation_kind", "extract_rich")
        config["parser"] = body.parser_type
        background_tasks.add_task(
            process_cdm_parsing,
            document_id=document.id,
            source_document_id=document.source_document_id,
            project_id=body.project_id,
            representation_kind=representation_kind,
            config=config,
            storage_service=storage_service,
            llamaparse_api_key=llamaparse_api_key,
            landingai_api_key=landingai_api_key,
        )

    return document


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


@router.post(
    "/{document_id}/parse-runs",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a new CDM parse run for a document",
)
async def create_document_parse_run(
    document_id: UUID,
    body: _ParseRunCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
):
    """Dispatch a new CDM parse run for an existing document."""
    from app.services.document_service import process_cdm_parsing

    document_repo = DocumentRepository(db)
    document = await document_repo.get_by_id(document_id, current_user.id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    if document.source_document_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document has no source_document_id; upload must be re-done via CDM path",
        )

    llamaparse_api_key, landingai_api_key = await _resolve_parser_key(
        db, current_user.id, body.parser_type
    )

    cfg = body.config or {}
    representation_kind = cfg.get("representation_kind", "extract_rich")
    parse_cfg = {k: v for k, v in cfg.items() if k != "representation_kind"}
    parse_cfg["parser"] = body.parser_type

    background_tasks.add_task(
        process_cdm_parsing,
        document_id=document_id,
        source_document_id=document.source_document_id,
        project_id=document.project_id,
        representation_kind=representation_kind,
        config=parse_cfg,
        storage_service=storage_service,
        llamaparse_api_key=llamaparse_api_key,
        landingai_api_key=landingai_api_key,
        force=True,
    )
    return {"status": "accepted"}


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


@router.post(
    "/{document_id}/probe",
    summary="Run DocumentProbe — classify PDF by page without parsing",
)
async def probe_document(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
) -> dict:
    """Classify a PDF by page using PyMuPDF — no parsing, no persistence."""
    try:
        content, _filename, _mime = await document_service.get_file_content(
            document_id=document_id,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        profile = DocumentProbe().run(
            pdf_path=Path(tmp_path),
            source_document_id=str(document_id),
        )
    finally:
        os.unlink(tmp_path)

    return profile.model_dump(mode="json")
