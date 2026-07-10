from __future__ import annotations
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.probe.config import ProbeConfig
from app.probe.report import ProbeReport
from app.routers.documents import get_document_service
from app.services.document_service import DocumentService
from app.services.exceptions import NotFoundError, ValidationError
from app.services.probe_service import ProbeService

router = APIRouter(prefix="/probe", tags=["probe"])


class ProbeRequest(BaseModel):
    document_id: UUID
    config: Optional[ProbeConfig] = None


@router.post("", response_model=ProbeReport, summary="Probe a document for parser-config evidence")
async def probe_document(
    body: ProbeRequest,
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
) -> ProbeReport:
    service = ProbeService(document_service)
    try:
        return await service.probe(
            document_id=body.document_id, user_id=current_user.id,
            config=body.config or ProbeConfig())
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
