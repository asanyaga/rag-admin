"""ExtractionResult transform API."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.extraction_result_repository import ExtractionResultRepository
from app.schemas.extraction_result import ExtractionResultResponse
from app.schemas.result_transform import (
    TransformApplyRequest,
    TransformPreviewRequest,
    TransformPreviewResponse,
)
from app.services.exceptions import NotFoundError
from app.services.extraction.transforms.base import TransformValidationError
from app.services.extraction.transforms.registry import get_transforms
from app.services.result_transform_service import ResultTransformService

router = APIRouter(tags=["result-transforms"])


def get_result_transform_service(db: AsyncSession = Depends(get_db)) -> ResultTransformService:
    return ResultTransformService(result_repo=ExtractionResultRepository(db))


@router.get("/result-transforms/catalog", summary="List available transforms")
async def transforms_catalog(
    current_user: User = Depends(get_current_active_user),
):
    return get_transforms()


@router.post(
    "/projects/{project_id}/result-transforms/preview",
    response_model=TransformPreviewResponse,
    summary="Preview a transform (no persistence)",
)
async def preview_transform(
    project_id: UUID,
    body: TransformPreviewRequest,
    current_user: User = Depends(get_current_active_user),
    service: ResultTransformService = Depends(get_result_transform_service),
):
    try:
        out = await service.preview(body.source_result_ids, body.transform_type, body.config)
        return TransformPreviewResponse(**out)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except TransformValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": e.code, "detail": e.detail},
        )


@router.post(
    "/projects/{project_id}/result-transforms/apply",
    response_model=ExtractionResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply a transform and persist a derived result",
)
async def apply_transform(
    project_id: UUID,
    body: TransformApplyRequest,
    current_user: User = Depends(get_current_active_user),
    service: ResultTransformService = Depends(get_result_transform_service),
):
    try:
        result = await service.apply(
            body.source_result_ids,
            body.transform_type,
            body.config,
            user_id=current_user.id,
            target_schema_id=body.target_schema_id,
        )
        return ExtractionResultResponse.from_orm_model(result)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except TransformValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": e.code, "detail": e.detail},
        )
