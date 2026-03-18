"""Parse results API router."""
from uuid import UUID
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.documents import get_storage_service
from app.models import User
from app.ports import StorageService
from app.repositories.document_repository import DocumentRepository
from app.repositories.parse_result_repository import ParseResultRepository
from app.schemas.parse_result import (
    ParseResultResponse,
    ParseResultListResponse,
    ParseRequest,
    ParserInfoResponse,
)
from app.services.parse_service import ParseService, process_document_parsing
from app.services.exceptions import NotFoundError
from app.adapters.parsing.registry import get_parser


router = APIRouter(tags=["parse-results"])


def get_parse_service(
    db: AsyncSession = Depends(get_db),
) -> ParseService:
    """Dependency to create ParseService."""
    return ParseService(
        parse_result_repo=ParseResultRepository(db),
        document_repo=DocumentRepository(db),
    )


@router.post(
    "/documents/{document_id}/parse",
    response_model=ParseResultResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-parse a document",
)
async def reparse_document(
    document_id: UUID,
    body: ParseRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    parse_service: ParseService = Depends(get_parse_service),
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
):
    """Trigger a re-parse of an existing document."""
    try:
        # Validate parser type
        parser = get_parser(body.parser_type)
        if parser is None and body.parser_type != "simple":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown parser type: {body.parser_type}",
            )

        if body.parser_type == "simple":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot re-parse with simple parser. Use document extraction instead.",
            )

        # Create pending parse result
        parse_result = await parse_service.create_parse_result(
            document_id=document_id,
            user_id=current_user.id,
            parser_type=body.parser_type,
            parser_config=body.config,
        )

        # Schedule background parsing
        parse_result_repo = ParseResultRepository(db)
        document_repo = DocumentRepository(db)
        background_tasks.add_task(
            process_document_parsing,
            parse_result_id=parse_result.id,
            parse_result_repo=parse_result_repo,
            document_repo=document_repo,
            storage_service=storage_service,
            parser=parser,
        )

        return parse_result

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/documents/{document_id}/parse-results",
    response_model=list[ParseResultListResponse],
    summary="List parse results for a document",
)
async def list_parse_results(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    parse_service: ParseService = Depends(get_parse_service),
):
    """List all parse results for a document."""
    return await parse_service.list_parse_results(document_id)


@router.get(
    "/parse-results/{result_id}",
    response_model=ParseResultResponse,
    summary="Get a parse result",
)
async def get_parse_result(
    result_id: UUID,
    current_user: User = Depends(get_current_active_user),
    parse_service: ParseService = Depends(get_parse_service),
):
    """Get full details of a parse result."""
    try:
        return await parse_service.get_parse_result(result_id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/parsers",
    response_model=list[ParserInfoResponse],
    summary="List available parsers",
)
async def list_parsers(
    current_user: User = Depends(get_current_active_user),
    parse_service: ParseService = Depends(get_parse_service),
):
    """Get list of available document parsers."""
    return await parse_service.get_parsers()
