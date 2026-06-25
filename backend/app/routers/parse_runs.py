"""Parse-runs API router — CDM read endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.models.document import Document as DocumentORM
from app.models.project import Project
from app.repositories.parse_run_repository import ParseRunRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.schemas.parse_run import (
    ParsedDocumentResponse,
    ParseRunResponse,
    RawPayloadResponse,
)

router = APIRouter(prefix="/parse-runs", tags=["parse-runs"])


async def _user_owns_source(
    db: AsyncSession, *, source_document_id: UUID, user_id: UUID
) -> bool:
    """True iff the user owns any Document pointing at this source_document_id."""
    result = await db.execute(
        select(DocumentORM.id)
        .join(DocumentORM.project)
        .where(
            and_(
                DocumentORM.source_document_id == source_document_id,
                Project.user_id == user_id,
            )
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


@router.get(
    "/{parse_run_id}",
    response_model=ParseRunResponse,
    summary="Get a single ParseRun by id",
    description=(
        "Return the execution row for one ParseRun. Used by the dedicated "
        "viewer route, which only has the run id (not its document id)."
    ),
)
async def get_parse_run(
    parse_run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    run = await ParseRunRepository(db).get(parse_run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ParseRun {parse_run_id} not found",
        )
    owns = await _user_owns_source(
        db, source_document_id=run.source_document_id, user_id=current_user.id
    )
    if not owns:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this ParseRun",
        )
    return ParseRunResponse.from_orm_row(run)


@router.get(
    "/{parse_run_id}/parsed-document",
    response_model=ParsedDocumentResponse,
    summary="Get the ParsedDocument content for a ParseRun",
    description=(
        "Return the full CDM content blob produced by a ParseRun. "
        "Returns 404 if the run has no associated ParsedDocument "
        "(e.g. the run failed)."
    ),
)
async def get_parsed_document_for_run(
    parse_run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    run = await ParseRunRepository(db).get(parse_run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ParseRun {parse_run_id} not found",
        )
    owns = await _user_owns_source(
        db, source_document_id=run.source_document_id, user_id=current_user.id
    )
    if not owns:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this ParseRun",
        )
    parsed = await ParsedDocumentRepository(db).get_by_run(parse_run_id)
    if parsed is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No ParsedDocument for ParseRun {parse_run_id}",
        )
    return ParsedDocumentResponse.from_orm_row(parsed)


@router.get(
    "/{parse_run_id}/raw-payload",
    response_model=RawPayloadResponse,
    summary="Get the verbatim parser SDK payload for a ParseRun",
    description=(
        "Return the raw parser-SDK response that produced this ParseRun, as "
        "captured at run time. Returns rawPayload: null for legacy runs or "
        "runs where no payload was captured (e.g. the parser SDK call failed)."
    ),
)
async def get_raw_payload_for_run(
    parse_run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    run = await ParseRunRepository(db).get(parse_run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ParseRun {parse_run_id} not found",
        )
    owns = await _user_owns_source(
        db, source_document_id=run.source_document_id, user_id=current_user.id
    )
    if not owns:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this ParseRun",
        )
    return RawPayloadResponse(raw_payload=run.raw_payload)


@router.delete(
    "/{parse_run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a ParseRun",
    description=(
        "Delete a ParseRun and its ParsedDocument (via DB cascade). "
        "Returns 409 if any index documents, classification runs, or extraction results "
        "still reference this run."
    ),
)
async def delete_parse_run(
    parse_run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ParseRunRepository(db)
    run = await repo.get(parse_run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ParseRun {parse_run_id} not found",
        )
    owns = await _user_owns_source(
        db, source_document_id=run.source_document_id, user_id=current_user.id
    )
    if not owns:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this ParseRun",
        )
    blockers = await repo.get_blockers(parse_run_id)
    if any(blockers.values()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Parse run has dependent entities that must be removed first.",
                "blockers": blockers,
            },
        )
    await repo.delete(run)
