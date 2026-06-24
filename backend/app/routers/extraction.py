"""Extraction API router."""
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
from app.models import User
from app.repositories.document_repository import DocumentRepository
from app.repositories.extraction_schema_repository import ExtractionSchemaRepository
from app.repositories.extraction_result_repository import ExtractionResultRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.repositories.provider_key_repository import ProviderKeyRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.dependencies.documents import get_storage_service
from app.schemas.extraction_result import (
    ExtractionSchemaCreate,
    ExtractionSchemaUpdate,
    ExtractionSchemaResponse,
    RunExtractionRequest,
    ExtractionResultResponse,
    ExtractionResultListResponse,
    ExtractorInfoResponse,
    LlmDefaultsResponse,
)
from app.services.extraction_service import ExtractionService, process_extraction
from app.services.exceptions import NotFoundError, ConflictError
from app.services.provider_key_service import resolve_api_key
from app.services.llm.factory import create_adapter
from app.adapters.extraction.registry import get_extractor
from app.adapters.extraction.pipeline import PipelineExtractor
from app.ports.data_extraction import DataExtractor


router = APIRouter(tags=["extraction"])


def _maybe_wrap_pipeline(
    inner: DataExtractor,
    preprocess: list[dict] | None,
    chunking: dict | None,
) -> DataExtractor:
    """Wrap inner extractor in a PipelineExtractor when pipeline config is present."""
    if not preprocess and not chunking:
        return inner
    max_tpm = (chunking or {}).get("maxTokensPerMinute")
    return PipelineExtractor(
        inner=inner,
        preprocess=preprocess,
        chunking=chunking,
        max_tokens_per_minute=int(max_tpm) if max_tpm is not None else None,
    )


def get_extraction_service(
    db: AsyncSession = Depends(get_db),
) -> ExtractionService:
    """Dependency to create ExtractionService."""
    return ExtractionService(
        schema_repo=ExtractionSchemaRepository(db),
        result_repo=ExtractionResultRepository(db),
        parsed_document_repo=ParsedDocumentRepository(db),
        document_repo=DocumentRepository(db),
    )


# --- Schema endpoints ---

@router.post(
    "/projects/{project_id}/extraction-schemas",
    response_model=ExtractionSchemaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an extraction schema",
)
async def create_extraction_schema(
    project_id: UUID,
    body: ExtractionSchemaCreate,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionService = Depends(get_extraction_service),
):
    try:
        return await service.create_schema(
            project_id=project_id,
            user_id=current_user.id,
            name=body.name,
            schema_definition=body.schema_definition,
            description=body.description,
            extraction_target=body.extraction_target,
        )
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "/projects/{project_id}/extraction-schemas",
    response_model=list[ExtractionSchemaResponse],
    summary="List extraction schemas for a project",
)
async def list_extraction_schemas(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionService = Depends(get_extraction_service),
):
    return await service.list_schemas(project_id, current_user.id)


@router.get(
    "/extraction-schemas/{schema_id}",
    response_model=ExtractionSchemaResponse,
    summary="Get an extraction schema",
)
async def get_extraction_schema(
    schema_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionService = Depends(get_extraction_service),
):
    try:
        return await service.get_schema(schema_id, current_user.id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put(
    "/extraction-schemas/{schema_id}",
    response_model=ExtractionSchemaResponse,
    summary="Update an extraction schema",
)
async def update_extraction_schema(
    schema_id: UUID,
    body: ExtractionSchemaUpdate,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionService = Depends(get_extraction_service),
):
    try:
        return await service.update_schema(
            schema_id=schema_id,
            user_id=current_user.id,
            name=body.name,
            description=body.description,
            schema_definition=body.schema_definition,
            extraction_target=body.extraction_target,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/extraction-schemas/{schema_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an extraction schema",
)
async def delete_extraction_schema(
    schema_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionService = Depends(get_extraction_service),
):
    try:
        await service.delete_schema(schema_id, current_user.id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- Extraction endpoints ---

@router.post(
    "/extractions/run",
    response_model=ExtractionResultResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run extraction on a CDM ParsedDocument",
)
async def run_extraction(
    body: RunExtractionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionService = Depends(get_extraction_service),
    db: AsyncSession = Depends(get_db),
):
    try:
        provider_key_repo = ProviderKeyRepository(db)

        if body.extraction_method == "llm":
            provider = (body.llm_config.provider if body.llm_config else None) or "ollama_local"
            api_key = await resolve_api_key(provider_key_repo, current_user.id, provider)
            if api_key is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No API key configured for provider '{provider}'",
                )
            adapter = create_adapter(provider, api_key)
            extractor = get_extractor(
                "llm",
                {},
                {
                    "source_document_repo": SourceDocumentRepository(db),
                    "storage_service": get_storage_service(),
                    "adapter": adapter,
                    "provider": provider,
                },
            )
        else:
            llama_key = await resolve_api_key(provider_key_repo, current_user.id, "llama_cloud")
            extractor = get_extractor(
                body.extraction_method,
                {"api_key": llama_key} if llama_key else {},
                {
                    "source_document_repo": SourceDocumentRepository(db),
                    "storage_service": get_storage_service(),
                },
            )

        extractor = _maybe_wrap_pipeline(extractor, body.preprocess, body.chunking)

        result = await service.run_extraction(
            parse_run_id=body.parse_run_id,
            extraction_schema_id=body.extraction_schema_id,
            extraction_method=body.extraction_method,
            user_id=current_user.id,
            config=body.config,
            llm_config=body.llm_config,
            user_prompt_template=body.user_prompt_template,
            timeout_minutes=body.timeout_minutes,
        )

        background_tasks.add_task(
            process_extraction,
            extraction_result_id=result.id,
            result_repo=ExtractionResultRepository(db),
            parsed_document_repo=ParsedDocumentRepository(db),
            extractor=extractor,
        )

        return result

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Result endpoints ---

@router.get(
    "/documents/{document_id}/extraction-results",
    response_model=list[ExtractionResultListResponse],
    summary="List extraction results for a document",
)
async def list_extraction_results(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionService = Depends(get_extraction_service),
):
    return await service.list_extraction_results(document_id)


@router.get(
    "/extraction-results/{result_id}",
    response_model=ExtractionResultResponse,
    summary="Get an extraction result",
)
async def get_extraction_result(
    result_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionService = Depends(get_extraction_service),
):
    try:
        return await service.get_extraction_result(result_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/extraction-results/{result_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an extraction result",
)
async def delete_extraction_result(
    result_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExtractionService = Depends(get_extraction_service),
):
    try:
        await service.delete_result(result_id, current_user.id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- Extractor info ---

@router.get(
    "/extractors",
    response_model=list[ExtractorInfoResponse],
    summary="List available extraction methods",
)
async def list_extractors(
    current_user: User = Depends(get_current_active_user),
    service: ExtractionService = Depends(get_extraction_service),
):
    return await service.get_extractors()


@router.get(
    "/extractors/llm/defaults",
    response_model=LlmDefaultsResponse,
    summary="Get default LLM extraction prompts",
)
async def get_llm_extraction_defaults(
    current_user: User = Depends(get_current_active_user),
):
    from app.adapters.extraction.llm import (
        DEFAULT_EXTRACTION_SYSTEM_PROMPT,
        DEFAULT_USER_PROMPT_TEMPLATE,
    )
    return LlmDefaultsResponse(
        systemPrompt=DEFAULT_EXTRACTION_SYSTEM_PROMPT,
        userPromptTemplate=DEFAULT_USER_PROMPT_TEMPLATE,
    )
