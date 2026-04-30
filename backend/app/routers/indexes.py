"""Indexes API router for index CRUD, processing, and chunk inspection."""
from uuid import UUID
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.models.document import Document
from app.repositories.index_repository import IndexRepository
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.provider_key_repository import ProviderKeyRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.schemas.index import (
    IndexCreate,
    IndexConfig,
    IndexUpdate,
    IndexResponse,
    IndexListResponse,
    IndexProcessingStatusResponse,
    AddParsedDocumentsRequest,
    ChunkPreview,
    ChunkPreviewRequest,
    ChunkPreviewResponse,
)
from app.schemas.chunk import (
    ChunkResponse,
    ChunkListResponse,
    ChunkSearchRequest,
)
from app.schemas.query import QueryRequest, QueryResponse
from app.schemas.playground import PlaygroundAnswerRequest
from app.services.answer_service import AnswerService
from app.services.chunk_service import ChunkService
from app.services.chunking_dispatcher import ChunkingDispatcher
from app.services.chunking_service import ChunkResult, get_chunking_service
from app.services.index_processing_service import (
    IndexProcessingService,
    process_index_background,
)
from app.services.index_service import IndexService
from app.services.query_service import QueryService
from app.services.source_resolution_service import SourceResolutionService
from app.services.trace_collector import TraceCollector
from app.services.exceptions import ConflictError, NotFoundError, ValidationError
from app.utils.encryption import decrypt

router = APIRouter(prefix="/projects/{project_id}/indexes", tags=["indexes"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_index_service(db: AsyncSession = Depends(get_db)) -> IndexService:
    """Dependency to create IndexService."""
    return IndexService(
        index_repo=IndexRepository(db),
        chunk_repo=ChunkRepository(db),
        parsed_doc_repo=ParsedDocumentRepository(db),
    )


def get_chunk_service(db: AsyncSession = Depends(get_db)) -> ChunkService:
    """Dependency to create ChunkService."""
    index_repo = IndexRepository(db)
    chunk_repo = ChunkRepository(db)
    return ChunkService(chunk_repo, index_repo)


def get_project_repo(db: AsyncSession = Depends(get_db)) -> ProjectRepository:
    """Dependency for project verification."""
    return ProjectRepository(db)


def get_document_repo(db: AsyncSession = Depends(get_db)) -> DocumentRepository:
    """Dependency for document verification."""
    return DocumentRepository(db)


def get_query_service(db: AsyncSession = Depends(get_db)) -> QueryService:
    """Dependency to create QueryService."""
    return QueryService(
        index_repo=IndexRepository(db),
        chunk_repo=ChunkRepository(db),
        provider_key_repo=ProviderKeyRepository(db),
    )


def get_answer_service(db: AsyncSession = Depends(get_db)) -> AnswerService:
    """Dependency to create AnswerService."""
    query_service = QueryService(
        index_repo=IndexRepository(db),
        chunk_repo=ChunkRepository(db),
        provider_key_repo=ProviderKeyRepository(db),
    )
    return AnswerService(query_service=query_service)


def get_provider_key_repo(db: AsyncSession = Depends(get_db)) -> ProviderKeyRepository:
    """Dependency for provider key lookups."""
    return ProviderKeyRepository(db)


async def verify_project_access(
    project_id: UUID,
    current_user: User,
    project_repo: ProjectRepository
) -> None:
    """Verify user has access to the project."""
    project = await project_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )


# ---------------------------------------------------------------------------
# Index CRUD
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=IndexResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create index",
    description="Create a new index with the specified configuration.",
)
async def create_index(
    project_id: UUID,
    data: IndexCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    service: IndexService = Depends(get_index_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
    db: AsyncSession = Depends(get_db),
):
    """Create a new index."""
    await verify_project_access(project_id, current_user, project_repo)

    try:
        index = await service.create_index(project_id, current_user.id, data)

        # If auto_process is True, start processing in background
        if data.auto_process:
            index_repo = IndexRepository(db)
            chunk_repo = ChunkRepository(db)
            provider_key_repo = ProviderKeyRepository(db)

            processing_service = IndexProcessingService(
                session=db,
                index_repo=index_repo,
                chunk_repo=chunk_repo,
                provider_key_repo=provider_key_repo
            )

            # Validate and update status to processing
            await processing_service.start_processing(
                index.id, project_id, current_user.id
            )

            # Add background task
            background_tasks.add_task(
                process_index_background,
                session=db,
                index_id=index.id,
                project_id=project_id,
                user_id=current_user.id,
            )

            # Refresh to get updated status
            index = await service.get_index(index.id, project_id)

        return index

    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "",
    response_model=list[IndexListResponse],
    summary="List indexes",
    description="List all indexes for a project.",
)
async def list_indexes(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: IndexService = Depends(get_index_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """List all indexes for a project."""
    await verify_project_access(project_id, current_user, project_repo)
    return await service.list_indexes(project_id)


@router.get(
    "/{index_id}",
    response_model=IndexResponse,
    summary="Get index",
    description="Get details of a specific index.",
)
async def get_index(
    project_id: UUID,
    index_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: IndexService = Depends(get_index_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Get a specific index."""
    await verify_project_access(project_id, current_user, project_repo)

    try:
        return await service.get_index(index_id, project_id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.patch(
    "/{index_id}",
    response_model=IndexResponse,
    summary="Update index",
    description="Update an index's name and/or description. Only works for indexes in 'created' status.",
)
async def update_index(
    project_id: UUID,
    index_id: UUID,
    data: IndexUpdate,
    current_user: User = Depends(get_current_active_user),
    service: IndexService = Depends(get_index_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Update an index."""
    await verify_project_access(project_id, current_user, project_repo)

    try:
        return await service.update_index(index_id, project_id, data)
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


@router.delete(
    "/{index_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete index",
    description="Delete an index and all its chunks.",
)
async def delete_index(
    project_id: UUID,
    index_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: IndexService = Depends(get_index_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Delete an index."""
    await verify_project_access(project_id, current_user, project_repo)

    try:
        await service.delete_index(index_id, project_id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# ---------------------------------------------------------------------------
# Index Processing
# ---------------------------------------------------------------------------

@router.post(
    "/{index_id}/process",
    response_model=IndexResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start processing",
    description="Start processing an index (chunking and embedding documents).",
)
async def start_processing(
    project_id: UUID,
    index_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    service: IndexService = Depends(get_index_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
    db: AsyncSession = Depends(get_db),
):
    """Start processing an index."""
    await verify_project_access(project_id, current_user, project_repo)

    try:
        index_repo = IndexRepository(db)
        chunk_repo = ChunkRepository(db)
        provider_key_repo = ProviderKeyRepository(db)

        processing_service = IndexProcessingService(
            session=db,
            index_repo=index_repo,
            chunk_repo=chunk_repo,
            provider_key_repo=provider_key_repo
        )

        # Validate and update status
        await processing_service.start_processing(index_id, project_id, current_user.id)

        # Add background task
        background_tasks.add_task(
            process_index_background,
            session=db,
            index_id=index_id,
            project_id=project_id,
            user_id=current_user.id,
        )

        return await service.get_index(index_id, project_id)

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


@router.post(
    "/{index_id}/retry",
    response_model=IndexResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry processing",
    description="Retry processing a failed index.",
)
async def retry_processing(
    project_id: UUID,
    index_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    service: IndexService = Depends(get_index_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
    db: AsyncSession = Depends(get_db),
):
    """Retry processing a failed index."""
    # Same as start_processing - it handles 'failed' status
    return await start_processing(
        project_id=project_id,
        index_id=index_id,
        background_tasks=background_tasks,
        current_user=current_user,
        service=service,
        project_repo=project_repo,
        db=db,
    )


@router.get(
    "/{index_id}/status",
    response_model=IndexProcessingStatusResponse,
    summary="Get processing status",
    description="Get detailed processing status for an index.",
)
async def get_processing_status(
    project_id: UUID,
    index_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: IndexService = Depends(get_index_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Get detailed processing status."""
    await verify_project_access(project_id, current_user, project_repo)

    try:
        return await service.get_processing_status(index_id, project_id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# ---------------------------------------------------------------------------
# Index Documents
# ---------------------------------------------------------------------------

@router.post(
    "/{index_id}/parsed-documents",
    response_model=IndexResponse,
    summary="Add parsed-documents",
    description="Add parsed-documents to an existing index.",
)
async def add_parsed_documents(
    project_id: UUID,
    index_id: UUID,
    data: AddParsedDocumentsRequest,
    current_user: User = Depends(get_current_active_user),
    service: IndexService = Depends(get_index_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.add_parsed_documents(index_id, project_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/{index_id}/documents/{document_id}",
    response_model=IndexResponse,
    summary="Remove document",
    description="Remove a document from an index.",
)
async def remove_document(
    project_id: UUID,
    index_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: IndexService = Depends(get_index_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Remove a document from an index."""
    await verify_project_access(project_id, current_user, project_repo)

    try:
        return await service.remove_document(index_id, project_id, document_id)
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


# ---------------------------------------------------------------------------
# Query / Playground
# ---------------------------------------------------------------------------

@router.post(
    "/{index_id}/query",
    response_model=QueryResponse,
    summary="Query index",
    description="Search an index using semantic, keyword, or hybrid search.",
)
async def query_index(
    project_id: UUID,
    index_id: UUID,
    data: QueryRequest,
    trace: bool = Query(False, description="Include query trace in response"),
    current_user: User = Depends(get_current_active_user),
    query_service: QueryService = Depends(get_query_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Query an index with semantic, keyword, or hybrid search."""
    await verify_project_access(project_id, current_user, project_repo)

    collector = None
    if trace:
        collector = TraceCollector(query=data.query, search_type=data.search_type)

    try:
        return await query_service.query_index(
            index_id, project_id, current_user.id, data, collector
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# Answer Playground (SSE streaming)
# ---------------------------------------------------------------------------

@router.post(
    "/{index_id}/playground/answer",
    summary="Answer playground (SSE)",
    description="Stream a RAG answer: retrieve chunks, build prompt, stream LLM response.",
)
async def playground_answer(
    project_id: UUID,
    index_id: UUID,
    data: PlaygroundAnswerRequest,
    trace: bool = Query(False, description="Include query trace as SSE event"),
    current_user: User = Depends(get_current_active_user),
    answer_service: AnswerService = Depends(get_answer_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
    provider_key_repo: ProviderKeyRepository = Depends(get_provider_key_repo),
):
    """Stream an answer for the playground via Server-Sent Events."""
    await verify_project_access(project_id, current_user, project_repo)

    # Resolve the LLM provider API key (reuses embedding key storage)
    llm_provider = data.llm_config.provider
    key_record = await provider_key_repo.get_for_provider(
        user_id=current_user.id,
        provider=llm_provider,
        project_id=project_id,
    )
    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"No API key configured for provider '{llm_provider}'. "
                "Add one in Settings → API Keys."
            ),
        )

    api_key = decrypt(key_record.api_key_encrypted)

    collector = None
    if trace:
        collector = TraceCollector(
            query=data.query,
            search_type=data.retrieval_config.search_type,
        )

    return StreamingResponse(
        answer_service.stream_answer(
            index_id=index_id,
            project_id=project_id,
            user_id=current_user.id,
            request=data,
            api_key=api_key,
            collector=collector,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Chunk Preview (Pre-Processing)
# ---------------------------------------------------------------------------

@router.post(
    "/preview-chunks",
    response_model=ChunkPreviewResponse,
    summary="Preview chunks",
    description="Preview how a document would be chunked without processing.",
)
async def preview_chunks(
    project_id: UUID,
    data: ChunkPreviewRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    project_repo: ProjectRepository = Depends(get_project_repo),
    document_repo: DocumentRepository = Depends(get_document_repo),
):
    """Preview chunks for a document.

    Accepts either `parsedDocumentId` (CDM path) or `documentId` (legacy /
    bridge path). The schema validator guarantees exactly one is set.
    """
    await verify_project_access(project_id, current_user, project_repo)

    # ── Path 1: parsedDocumentId supplied (CDM path) ─────────────────────────
    if data.parsed_document_id is not None:
        parsed_doc_repo = ParsedDocumentRepository(db)
        parsed_doc = await parsed_doc_repo.get_by_run(data.parsed_document_id)
        if parsed_doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parsed document {data.parsed_document_id} not found",
            )
        # Scope-check: verify the parsed-doc belongs to a document in this project.
        result = await db.execute(
            select(Document.id).where(
                Document.source_document_id == parsed_doc.source_document_id,
                Document.project_id == project_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parsed document {data.parsed_document_id} not found",
            )
        return await _preview_via_seam(
            parsed_document_id=data.parsed_document_id,
            config=data.config,
            max_chunks=data.max_chunks,
            source_document_id=None,
            source_filename=None,
            db=db,
        )

    # ── Path 2: documentId supplied (legacy / bridge path) ───────────────────
    assert data.document_id is not None  # guaranteed by model_validator
    document = await document_repo.get_by_id(data.document_id, current_user.id)
    if not document or document.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {data.document_id} not found",
        )

    # Legacy raw_text path: untouched, uses extracted_text directly.
    if data.config.source_representation == "raw_text":
        if not document.extracted_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document has no extracted text",
            )
        chunking_service = get_chunking_service()
        return chunking_service.preview_chunks(
            text=document.extracted_text,
            config=data.config,
            max_chunks=data.max_chunks,
        )

    # CDM bridge: resolve the latest parsed-doc for this document.
    parsed_doc_repo = ParsedDocumentRepository(db)
    parsed_doc = await parsed_doc_repo.get_latest_for_document(data.document_id)
    if parsed_doc is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No succeeded parse run found for this document. "
                "Run a parse job before previewing CDM chunks."
            ),
        )
    return await _preview_via_seam(
        parsed_document_id=parsed_doc.parse_run_id,
        config=data.config,
        max_chunks=data.max_chunks,
        source_document_id=None,
        source_filename=None,
        db=db,
    )


async def _preview_via_seam(
    *,
    parsed_document_id: UUID,
    config: IndexConfig,
    max_chunks: int,
    source_document_id: str | None,
    source_filename: str | None,
    db: AsyncSession,
) -> ChunkPreviewResponse:
    """Resolve a parsed-document via the seam and return a preview response."""
    try:
        source = await SourceResolutionService(db).resolve(
            parsed_document_id=parsed_document_id,
            source_representation=config.source_representation,  # type: ignore[arg-type]  # caller guarantees source_representation != "raw_text"
        )
        dispatcher = ChunkingDispatcher()
        chunks = dispatcher.dispatch(
            source=source,
            config=config,
            source_document_id=source_document_id,
            source_filename=source_filename,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc

    return _project_to_preview_response(chunks, config, max_chunks)


def _project_to_preview_response(
    chunks: list[ChunkResult],
    config: IndexConfig,
    max_chunks: int,
) -> ChunkPreviewResponse:
    """Build a ChunkPreviewResponse from a list of ChunkResult objects."""
    if not chunks:
        return ChunkPreviewResponse(
            total_chunks_estimate=0,
            avg_chunk_size_chars=0.0,
            avg_chunk_size_tokens=0.0,
            min_chunk_size_chars=0,
            max_chunk_size_chars=0,
            preview_chunks=[],
        )

    char_counts = [c.char_count for c in chunks]
    token_counts = [c.token_count for c in chunks]

    avg_chars = sum(char_counts) / len(char_counts)
    avg_tokens = sum(token_counts) / len(token_counts)

    preview: list[ChunkPreview] = []
    for i, chunk in enumerate(chunks[:max_chunks]):
        overlap_start = 0
        if i > 0 and config.chunk_overlap > 0:
            overlap_start = min(config.chunk_overlap, chunk.char_count // 2)
        overlap_end = 0
        if i < len(chunks) - 1 and config.chunk_overlap > 0:
            overlap_end = min(config.chunk_overlap, chunk.char_count // 2)
        preview.append(ChunkPreview(
            index=chunk.chunk_index,
            content=chunk.content,
            char_count=chunk.char_count,
            token_count=chunk.token_count,
            overlap_start_chars=overlap_start,
            overlap_end_chars=overlap_end,
        ))

    return ChunkPreviewResponse(
        total_chunks_estimate=len(chunks),
        avg_chunk_size_chars=round(avg_chars, 1),
        avg_chunk_size_tokens=round(avg_tokens, 1),
        min_chunk_size_chars=min(char_counts),
        max_chunk_size_chars=max(char_counts),
        preview_chunks=preview,
    )


# ---------------------------------------------------------------------------
# Chunk Inspection
# ---------------------------------------------------------------------------

@router.get(
    "/{index_id}/chunks",
    response_model=ChunkListResponse,
    summary="List chunks",
    description="List chunks in an index with pagination.",
)
async def list_chunks(
    project_id: UUID,
    index_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize", description="Items per page"),
    search: str | None = Query(None, description="Search query for chunk content"),
    current_user: User = Depends(get_current_active_user),
    service: ChunkService = Depends(get_chunk_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """List chunks in an index."""
    await verify_project_access(project_id, current_user, project_repo)

    try:
        if search:
            return await service.search_chunks(
                index_id, project_id, search, page, page_size
            )
        return await service.list_chunks(index_id, project_id, page, page_size)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get(
    "/{index_id}/chunks/{chunk_id}",
    response_model=ChunkResponse,
    summary="Get chunk",
    description="Get details of a specific chunk.",
)
async def get_chunk(
    project_id: UUID,
    index_id: UUID,
    chunk_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ChunkService = Depends(get_chunk_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Get a specific chunk."""
    await verify_project_access(project_id, current_user, project_repo)

    try:
        return await service.get_chunk(chunk_id, index_id, project_id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get(
    "/{index_id}/stats",
    summary="Get index statistics",
    description="Get computed statistics for an index.",
)
async def get_index_stats(
    project_id: UUID,
    index_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: IndexService = Depends(get_index_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Get index statistics."""
    await verify_project_access(project_id, current_user, project_repo)

    try:
        index = await service.get_index(index_id, project_id)
        return index.stats
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
