"""Golden Sets API router."""
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.golden_set_repository import GoldenSetRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.provider_key_repository import ProviderKeyRepository
from app.schemas.golden_set import (
    GoldenSetCreate,
    GoldenSetUpdate,
    GoldenSetResponse,
    GoldenSetDetailResponse,
    QueryCreate,
    QueryUpdate,
    QueryResponse,
    SourceCreate,
    SourceResponse,
    GenerateGoldenSetRequest,
    BulkReviewRequest,
    ImportParseResponse,
    ImportValidQuery,
    ImportParsedSource,
    ImportParseError,
    ImportDuplicate,
    ImportParseSummary,
    ImportConfirmRequest,
    ImportConfirmResponse,
)
from app.services.golden_set_service import GoldenSetService
from app.services.golden_set_generation_service import GoldenSetGenerationService
from app.services.golden_set_import_service import GoldenSetImportService
from app.services.exceptions import NotFoundError, ValidationError

router = APIRouter(
    prefix="/projects/{project_id}/golden-sets",
    tags=["golden_sets"],
)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_golden_set_service(db: AsyncSession = Depends(get_db)) -> GoldenSetService:
    return GoldenSetService(
        golden_set_repo=GoldenSetRepository(db),
        document_repo=DocumentRepository(db),
    )


def get_generation_service(db: AsyncSession = Depends(get_db)) -> GoldenSetGenerationService:
    return GoldenSetGenerationService(
        golden_set_repo=GoldenSetRepository(db),
        document_repo=DocumentRepository(db),
        provider_key_repo=ProviderKeyRepository(db),
    )


def get_project_repo(db: AsyncSession = Depends(get_db)) -> ProjectRepository:
    return ProjectRepository(db)


async def verify_project_access(
    project_id: UUID,
    current_user: User,
    project_repo: ProjectRepository,
) -> None:
    project = await project_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )


# ---------------------------------------------------------------------------
# Background task helper
# ---------------------------------------------------------------------------

async def execute_generation_background(
    db: AsyncSession,
    gs_id: UUID,
    project_id: UUID,
    user_id: UUID,
) -> None:
    """Background task to execute golden set generation."""
    service = GoldenSetGenerationService(
        golden_set_repo=GoldenSetRepository(db),
        document_repo=DocumentRepository(db),
        provider_key_repo=ProviderKeyRepository(db),
    )
    await service.execute_generation(gs_id, project_id, user_id)


# ---------------------------------------------------------------------------
# Golden Set CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=list[GoldenSetResponse])
async def list_golden_sets(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    return await service.list(project_id)


@router.post("", response_model=GoldenSetResponse, status_code=status.HTTP_201_CREATED)
async def create_golden_set(
    project_id: UUID,
    data: GoldenSetCreate,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    return await service.create(project_id, current_user.id, data)


@router.get("/{gs_id}", response_model=GoldenSetDetailResponse)
async def get_golden_set(
    project_id: UUID,
    gs_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.get(gs_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{gs_id}", response_model=GoldenSetResponse)
async def update_golden_set(
    project_id: UUID,
    gs_id: UUID,
    data: GoldenSetUpdate,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.update(gs_id, project_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{gs_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_golden_set(
    project_id: UUID,
    gs_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        await service.delete(gs_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

@router.post("/{gs_id}/generate", response_model=GoldenSetDetailResponse)
async def generate_golden_set(
    project_id: UUID,
    gs_id: UUID,
    data: GenerateGoldenSetRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    gen_service: GoldenSetGenerationService = Depends(get_generation_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        await gen_service.trigger_generation(
            gs_id=gs_id,
            project_id=project_id,
            user_id=current_user.id,
            document_ids=data.document_ids,
            llm_provider=data.llm_provider,
            llm_model=data.llm_model,
            queries_per_document=data.queries_per_document,
            question_types=data.question_types,
            temperature=data.temperature,
        )

        # Execute in background
        background_tasks.add_task(
            execute_generation_background,
            db=db,
            gs_id=gs_id,
            project_id=project_id,
            user_id=current_user.id,
        )

        return await service.get(gs_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------------------------------------------------------------------------
# Bulk Review
# ---------------------------------------------------------------------------

@router.post("/{gs_id}/queries/bulk-review")
async def bulk_review_queries(
    project_id: UUID,
    gs_id: UUID,
    data: BulkReviewRequest,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        count = await service.bulk_review(gs_id, project_id, data)
        return {"updated": count}
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

@router.post("/{gs_id}/import/parse", response_model=ImportParseResponse)
async def parse_import(
    project_id: UUID,
    gs_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id, current_user, project_repo)
    # Verify golden set exists
    try:
        await service.get(gs_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    content = await file.read()
    filename = file.filename or "unknown.csv"

    import_service = GoldenSetImportService(db)
    try:
        result = await import_service.parse_file(content, filename, project_id, gs_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return ImportParseResponse(
        valid_queries=[
            ImportValidQuery(
                row=q.row,
                query_text=q.query_text,
                sources=[
                    ImportParsedSource(
                        document_name=s.document_name,
                        document_id=s.document_id,
                        pages=s.pages,
                        resolved=s.resolved,
                    )
                    for s in q.sources
                ],
                is_duplicate=q.is_duplicate,
            )
            for q in result.valid_queries
        ],
        errors=[
            ImportParseError(row=e.row, query_text=e.query_text, error=e.error)
            for e in result.errors
        ],
        duplicates=[
            ImportDuplicate(
                row=d.row,
                query_text=d.query_text,
                existing_query_id=d.existing_query_id,
            )
            for d in result.duplicates
        ],
        summary=ImportParseSummary(
            total_rows=result.total_rows,
            valid_count=len(result.valid_queries),
            error_count=len(result.errors),
            duplicate_count=len(result.duplicates),
        ),
    )


@router.post(
    "/{gs_id}/import/confirm",
    response_model=ImportConfirmResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_import(
    project_id: UUID,
    gs_id: UUID,
    data: ImportConfirmRequest,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        await service.get(gs_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    import_service = GoldenSetImportService(db)
    queries_data = [
        {
            "query_text": q.query_text,
            "sources": [
                {
                    "document_id": s.document_id,
                    "locator": s.locator,
                }
                for s in q.sources
            ],
        }
        for q in data.queries
    ]

    try:
        created = await import_service.import_queries(gs_id, queries_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}",
        )

    return ImportConfirmResponse(imported_count=len(created))


# ---------------------------------------------------------------------------
# Query CRUD
# ---------------------------------------------------------------------------

@router.post("/{gs_id}/queries", response_model=QueryResponse, status_code=status.HTTP_201_CREATED)
async def add_query(
    project_id: UUID,
    gs_id: UUID,
    data: QueryCreate,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.add_query(gs_id, project_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{gs_id}/queries/{query_id}", response_model=QueryResponse)
async def update_query(
    project_id: UUID,
    gs_id: UUID,
    query_id: UUID,
    data: QueryUpdate,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.update_query(gs_id, project_id, query_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{gs_id}/queries/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_query(
    project_id: UUID,
    gs_id: UUID,
    query_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        await service.delete_query(gs_id, project_id, query_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ---------------------------------------------------------------------------
# Source CRUD
# ---------------------------------------------------------------------------

@router.post(
    "/{gs_id}/queries/{query_id}/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_source(
    project_id: UUID,
    gs_id: UUID,
    query_id: UUID,
    data: SourceCreate,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.add_source(gs_id, project_id, query_id, current_user.id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/{gs_id}/queries/{query_id}/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_source(
    project_id: UUID,
    gs_id: UUID,
    query_id: UUID,
    source_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: GoldenSetService = Depends(get_golden_set_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        await service.delete_source(gs_id, project_id, query_id, source_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
