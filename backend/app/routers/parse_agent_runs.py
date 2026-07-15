"""Parse-agent runs API: start a run from an upload, read its trace."""
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.documents import get_parsing_service, get_storage_service
from app.models import User
from app.ports import StorageService
from app.repositories.parse_agent_run_repository import ParseAgentRunRepository
from app.repositories.project_repository import ProjectRepository
from app.routers.documents import _resolve_parser_key  # reuse BYOK key resolution
from app.schemas.parse_agent_run import (
    ParseAgentRunCreatedResponse,
    ParseAgentRunDetailResponse,
    ParseAgentRunStepResponse,
    ParseAgentRunSummary,
)
from app.services.parse_agent.engine import run_parse_agent
from app.services.parse_agent.nodes import GRAPH_NODES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/parse-agent-runs", tags=["parse-agent-runs"])


@router.post("", response_model=ParseAgentRunCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_run(
    background_tasks: BackgroundTasks,
    project_id: UUID = Form(...),
    parser_type: str = Form("simple"),
    parse_config: str | None = Form(None),
    file: UploadFile = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
):
    project = await ProjectRepository(db).get_by_id(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    llamaparse_api_key, landingai_api_key = await _resolve_parser_key(
        db, current_user.id, parser_type
    )

    config_dict = {}
    if parse_config:
        try:
            config_dict = json.loads(parse_config)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON in parse_config",
            )
    representation_kind = config_dict.pop("representation_kind", "extract_rich")
    config_dict["parser"] = parser_type

    file_content = await file.read()
    filename = file.filename or "upload.pdf"

    parsing_service = get_parsing_service(db)
    source = await parsing_service.ensure_source_document(
        bytes_=file_content, filename=filename, mime_type=file.content_type or "application/pdf",
    )

    run = await ParseAgentRunRepository(db).create_run(
        project_id=project_id, source_document_id=UUID(source.id),
        started_at=datetime.now(timezone.utc),
    )

    background_tasks.add_task(
        run_parse_agent,
        run_id=run.id, source_document_id=UUID(source.id), file_path=source.storage_uri,
        project_id=project_id, config=config_dict, representation_kind=representation_kind,
        storage_service=storage_service,
        llamaparse_api_key=llamaparse_api_key, landingai_api_key=landingai_api_key,
    )
    return ParseAgentRunCreatedResponse(run_id=run.id)


@router.get("/{run_id}", response_model=ParseAgentRunDetailResponse)
async def get_run(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ParseAgentRunRepository(db)
    run = await repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    project = await ProjectRepository(db).get_by_id(run.project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    steps = await repo.list_steps(run_id)
    return ParseAgentRunDetailResponse(
        run=ParseAgentRunSummary.model_validate(run),
        steps=[ParseAgentRunStepResponse.model_validate(s) for s in steps],
        graph_nodes=GRAPH_NODES,
    )
