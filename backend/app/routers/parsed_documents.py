"""Project-scoped parsed-documents router.

Exposes `GET /projects/{project_id}/parsed-documents` — the picker data source
for the parsed-document selector in the index-creation wizard. Supports family
filtering (`parser` + `parseConfigHash`), representation filtering, and a
`latestPerSource` toggle that surfaces older runs in the same family for
non-determinism debugging.
"""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.parsed_document import ParsedDocumentListItem


router = APIRouter(prefix="/projects/{project_id}/parsed-documents", tags=["parsed-documents"])


@router.get(
    "",
    response_model=list[ParsedDocumentListItem],
    summary="List parsed documents in a project",
    description=(
        "Returns parsed-documents for documents in the project, newest first. "
        "Supply `parser` + `parseConfigHash` together to restrict to one family. "
        "`representation` filters to parsed-docs that populate that segment. "
        "`latestPerSource=true` (default) keeps only the newest parse_run per source "
        "document; set false to see every successful run in the family."
    ),
)
async def list_parsed_documents(
    project_id: UUID,
    parser: str | None = Query(None),
    parse_config_hash: str | None = Query(None, alias="parseConfigHash"),
    representation: Literal["full_text", "full_markdown", "block"] | None = Query(None),
    latest_per_source: bool = Query(True, alias="latestPerSource"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[ParsedDocumentListItem]:
    if (parser is None) != (parse_config_hash is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="parser and parseConfigHash must be supplied together",
        )

    project = await ProjectRepository(db).get_by_id(project_id, current_user.id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    rows = await ParsedDocumentRepository(db).list_for_project(
        project_id,
        parser=parser,
        parse_config_hash=parse_config_hash,
        representation=representation,
        latest_per_source=latest_per_source,
    )
    return [
        ParsedDocumentListItem(
            id=row.parse_run_id,
            parse_run_id=row.parse_run_id,
            parser=row.parser,
            parse_config_hash=row.parse_config_hash,
            source_document_id=row.source_document_id,
            source_filename=row.source_filename,
            has_full_markdown=row.has_full_markdown,
            block_count=row.block_count,
            parsed_at=row.parsed_at,
        )
        for row in rows
    ]
