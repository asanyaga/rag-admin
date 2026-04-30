"""Project-scoped parse-run config families router.

Exposes `GET /projects/{project_id}/parse-runs/configs` — distinct
`(parser, parse_config_hash)` combinations that have at least one successful
parse run for any document in the project. Powers the parser-config family
selector in the index-creation wizard.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.parse_run_repository import ParseRunRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.parsed_document import ParseConfigOption


router = APIRouter(prefix="/projects/{project_id}/parse-runs", tags=["parse-runs"])


@router.get(
    "/configs",
    response_model=list[ParseConfigOption],
    summary="List parse-config families",
    description=(
        "Distinct (parser, parse_config_hash) families with at least one successful "
        "parse run across the project's documents. Used by the parser-config family "
        "selector in the index-creation wizard."
    ),
)
async def list_parse_run_configs(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[ParseConfigOption]:
    project = await ProjectRepository(db).get_by_id(project_id, current_user.id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    rows = await ParseRunRepository(db).list_distinct_configs_for_project(project_id)
    return [
        ParseConfigOption(
            parser=row.parser,
            parse_config_hash=row.parse_config_hash,
            config=row.config,
            parsed_document_count=row.parsed_document_count,
            has_full_markdown=row.has_full_markdown,
            latest_parsed_at=row.latest_parsed_at,
        )
        for row in rows
    ]
