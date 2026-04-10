"""Agent API router — receipt processing pipeline endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.agent_receipt_repository import AgentReceiptRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.extraction_schema_repository import ExtractionSchemaRepository
from app.schemas.agent import (
    StartProcessingRequest,
    SubmitReviewRequest,
    AgentReceiptResponse,
    AgentReceiptListItem,
)
from app.services.agent.service import AgentService
from app.services.exceptions import NotFoundError


router = APIRouter(tags=["agent"])


def get_agent_service(
    db: AsyncSession = Depends(get_db),
) -> AgentService:
    """Dependency to create AgentService with checkpointer from app state."""
    from app.main import app
    checkpointer = app.state.agent_checkpointer

    return AgentService(
        receipt_repo=AgentReceiptRepository(db),
        document_repo=DocumentRepository(db),
        schema_repo=ExtractionSchemaRepository(db),
        checkpointer=checkpointer,
    )


@router.post(
    "/agent/projects/{project_id}/receipts",
    response_model=AgentReceiptResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start processing a receipt",
)
async def start_processing(
    project_id: UUID,
    body: StartProcessingRequest,
    current_user: User = Depends(get_current_active_user),
    service: AgentService = Depends(get_agent_service),
):
    try:
        return await service.start_processing(
            project_id=project_id,
            document_id=body.document_id,
            extraction_schema_id=body.extraction_schema_id,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/agent/projects/{project_id}/receipts",
    response_model=list[AgentReceiptListItem],
    summary="List receipts for a project",
)
async def list_receipts(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: AgentService = Depends(get_agent_service),
):
    return await service.list_receipts(project_id)


@router.get(
    "/agent/receipts/{receipt_id}",
    response_model=AgentReceiptResponse,
    summary="Get a receipt",
)
async def get_receipt(
    receipt_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: AgentService = Depends(get_agent_service),
):
    try:
        return await service.get_receipt(receipt_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/agent/receipts/{receipt_id}/review",
    response_model=AgentReceiptResponse,
    summary="Submit review for a receipt",
)
async def submit_review(
    receipt_id: UUID,
    body: SubmitReviewRequest,
    current_user: User = Depends(get_current_active_user),
    service: AgentService = Depends(get_agent_service),
):
    try:
        return await service.submit_review(
            receipt_id=receipt_id,
            action=body.action,
            data=body.data,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
