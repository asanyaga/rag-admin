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
from app.models.parse_result import ParseResultStatus


_CDM_PARSER_TYPES = frozenset({"llamaparse", "landing_ai"})

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
    from app.config import settings
    from app.dependencies.documents import get_llamaparse_client, get_landingai_client
    from app.repositories.parse_run_repository import ParseRunRepository
    from app.repositories.parsed_document_repository import ParsedDocumentRepository
    from app.repositories.source_document_repository import SourceDocumentRepository
    from app.services.document_service import process_cdm_parsing

    try:
        # Only consult the legacy registry for non-CDM, non-simple parsers.
        # get_parser raises ValueError for unknown types, caught below → 400.
        parser = None
        if body.parser_type not in ("simple", *_CDM_PARSER_TYPES):
            parser = get_parser(body.parser_type)

        if body.parser_type == "simple":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot re-parse with simple parser. Use document extraction instead.",
            )

        # Create pending parse result (also surfaces 404 if doc missing)
        parse_result = await parse_service.create_parse_result(
            document_id=document_id,
            user_id=current_user.id,
            parser_type=body.parser_type,
            parser_config=body.config,
        )

        parse_result_repo = ParseResultRepository(db)
        document_repo = DocumentRepository(db)

        document = await document_repo.get_by_id_unscoped(document_id)
        use_cdm = (
            settings.USE_CDM_PARSER
            and body.parser_type in _CDM_PARSER_TYPES
            and document is not None
            and document.source_document_id is not None
        )

        if use_cdm:
            # CDM owns the new run lifecycle. Mark the legacy placeholder completed
            # immediately so the 10-min stale reaper doesn't flip the document to
            # failed. The CDM RunTimeline is the source of truth for re-parse runs.
            parse_result = await parse_result_repo.update_status(
                parse_result.id,
                ParseResultStatus.completed,
                "Re-parse delegated to CDM ParseRun timeline.",
            )
            cfg = body.config or {}
            representation_kind = cfg.get("representation_kind", "extract_rich")
            parse_cfg = {k: v for k, v in cfg.items() if k != "representation_kind"}
            parse_cfg["parser"] = body.parser_type
            background_tasks.add_task(
                process_cdm_parsing,
                document_id=document_id,
                source_document_id=document.source_document_id,
                project_id=document.project_id,
                representation_kind=representation_kind,
                config=parse_cfg,
                document_repo=document_repo,
                parse_run_repo=ParseRunRepository(db),
                parsed_doc_repo=ParsedDocumentRepository(db),
                source_doc_repo=SourceDocumentRepository(db),
                storage_service=storage_service,
                llamaparse_client=get_llamaparse_client(),
                landingai_client=get_landingai_client(),
            )
            return ParseResultResponse.from_orm_model(parse_result)

        # Legacy path
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
