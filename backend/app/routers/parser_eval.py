"""Parser Evaluation API router."""
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.documents import get_parsing_service, get_storage_service
from app.models import User
from app.repositories.parser_eval_repository import ParserEvalRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.schemas.parser_eval import (
    CaseCreate, CaseResponse, RunCreate, RunResponse, ResultResponse,
)
from app.services.exceptions import NotFoundError
from app.services.parser_eval.service import ParserEvalService

router = APIRouter(tags=["parser_eval"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def _service(db: AsyncSession) -> ParserEvalService:
    return ParserEvalService(
        repo=ParserEvalRepository(db),
        source_doc_repo=SourceDocumentRepository(db),
        parsing_service=get_parsing_service(db),
        storage=get_storage_service(),
    )


def get_service(db: AsyncSession = Depends(get_db)) -> ParserEvalService:
    return _service(db)


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
# Background task
# ---------------------------------------------------------------------------

async def execute_run_background(db: AsyncSession, run_id: UUID) -> None:
    """Background task to execute a parser-eval run.

    Reuses the request-scoped session (mirrors extraction_eval's background task) so
    that tests overriding `get_db` still hit the test database rather than production.
    """
    await _service(db).execute_run(run_id)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/parser-eval/cases", response_model=CaseResponse)
async def create_case(
    project_id: UUID,
    data: CaseCreate,
    current_user: User = Depends(get_current_active_user),
    service: ParserEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.create_case(project_id, current_user.id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/projects/{project_id}/parser-eval/cases", response_model=list[CaseResponse])
async def list_cases(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ParserEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    return await service.list_cases(project_id)


@router.post(
    "/projects/{project_id}/parser-eval/runs",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_run(
    project_id: UUID,
    data: RunCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    service: ParserEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        run = await service.create_run(project_id, current_user.id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    background_tasks.add_task(execute_run_background, db=db, run_id=run.id)
    return run


@router.get("/projects/{project_id}/parser-eval/runs", response_model=list[RunResponse])
async def list_runs(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ParserEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    return await service.list_runs(project_id)


@router.get(
    "/projects/{project_id}/parser-eval/runs/{run_id}/results",
    response_model=list[ResultResponse],
)
async def get_results(
    project_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ParserEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.get_results(run_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
