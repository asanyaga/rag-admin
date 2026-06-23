"""Source Documents API router."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.source_document_repository import SourceDocumentRepository
from app.schemas.source_document import SourceDocumentResponse

router = APIRouter(prefix="/source-documents", tags=["source-documents"])


@router.get("", response_model=list[SourceDocumentResponse])
async def list_source_documents(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[SourceDocumentResponse]:
    """List all source documents at tenant level with project reference counts."""
    repo = SourceDocumentRepository(db)
    rows = await repo.list_all()
    return [
        SourceDocumentResponse(
            id=sd.id,
            sha256=sd.sha256,
            filename=sd.filename,
            mime_type=sd.mime_type,
            byte_size=sd.byte_size,
            created_at=sd.created_at,
            project_count=count,
        )
        for sd, count in rows
    ]
