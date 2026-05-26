"""Classification API — two routers mounted at different prefixes in main.py."""
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.classification_run_repository import (
    ClassificationRunCreate,
    ClassificationRunRepository,
)
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.provider_key_repository import ProviderKeyRepository
from app.schemas.classification import (
    AnnotatedBlockResponse,
    ClassificationRegionResponse,
    ClassificationRunCreateRequest,
    ClassificationRunResponse,
)
from app.services.classification.service import ClassificationService
from app.services.llm.registry import LLMRegistry
from app.services.llm.ollama_adapter import OllamaAdapter
from app.services.llm.groq_adapter import GroqAdapter
from app.services.provider_key_service import resolve_api_key

logger = logging.getLogger(__name__)

# Mounted at /api/v1/documents
documents_router = APIRouter(prefix="/documents", tags=["classification"])

# Mounted at /api/v1/classification-runs
runs_router = APIRouter(prefix="/classification-runs", tags=["classification"])


def _classification_provider_to_byok(llm_provider: str) -> str | None:
    """Map classification LLM provider names to BYOK provider IDs."""
    return {"groq": "groq", "ollama_cloud": "ollama_cloud"}.get(llm_provider)


def _build_llm_registry(provider: str, api_key: str | None) -> LLMRegistry:
    """Build a per-request LLM registry with the resolved API key."""
    registry = LLMRegistry()
    if provider == "ollama_local":
        registry.register(
            "ollama_local",
            OllamaAdapter(base_url=settings.OLLAMA_LOCAL_BASE_URL, api_key="ollama"),
        )
    elif provider == "ollama_cloud" and api_key:
        registry.register(
            "ollama_cloud",
            OllamaAdapter(base_url=settings.OLLAMA_CLOUD_BASE_URL, api_key=api_key),
        )
    elif provider == "groq" and api_key:
        registry.register("groq", GroqAdapter(api_key=api_key))
    return registry


async def _run_classification_background(
    run_id: UUID,
    parse_run_id: UUID,
    labels: list[str],
    llm_provider: str,
    llm_model: str,
    batch_size: int,
    batch_overlap: int,
    api_key: str | None,
) -> None:
    from app.cdm.models import ParsedDocument as CDMParsedDocument

    try:
        async with AsyncSessionLocal() as session:
            repo = ClassificationRunRepository(session)
            pd_repo = ParsedDocumentRepository(session)

            pd_orm = await pd_repo.get_by_run(parse_run_id)
            if pd_orm is None:
                await repo.update_status(run_id=run_id, status="failed", error="ParsedDocument not found")
                return

            doc = CDMParsedDocument.model_validate(pd_orm.content)
            registry = _build_llm_registry(llm_provider, api_key)
            service = ClassificationService(repo=repo, llm_registry=registry)

            await service.execute(
                run_id=run_id,
                doc=doc,
                labels=labels,
                llm_provider=llm_provider,
                llm_model=llm_model,
                batch_size=batch_size,
                batch_overlap=batch_overlap,
            )
    except Exception:
        logger.exception("Classification background task failed for run %s", run_id)
        # Open a fresh session to guarantee the status update commits even if
        # the original session was left in a dirty state.
        async with AsyncSessionLocal() as recovery_session:
            recovery_repo = ClassificationRunRepository(recovery_session)
            run = await recovery_repo.get(run_id)
            if run and run.status == "running":
                await recovery_repo.update_status(run_id=run_id, status="failed", error="Internal error — check server logs")


def _to_run_response(run, regions=None) -> ClassificationRunResponse:
    return ClassificationRunResponse(
        id=run.id,
        parseRunId=run.parse_run_id,
        documentId=run.document_id,
        labelsRequested=run.labels_requested,
        llmProvider=run.llm_provider,
        llmModel=run.llm_model,
        status=run.status,
        error=run.error,
        batchSize=run.batch_size,
        batchOverlap=run.batch_overlap,
        inputTokens=run.input_tokens,
        outputTokens=run.output_tokens,
        durationMs=run.duration_ms,
        createdAt=run.created_at,
        regions=[
            ClassificationRegionResponse(
                id=r.id,
                label=r.label,
                pageStart=r.page_start,
                pageEnd=r.page_end,
                blockIds=r.block_ids,
                confidence=r.confidence,
                reasoning=r.reasoning,
                source=r.source,
            )
            for r in (regions or [])
        ],
    )


@documents_router.post(
    "/{document_id}/classification-runs",
    response_model=ClassificationRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_classification_run(
    document_id: UUID,
    body: ClassificationRunCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    doc_repo = DocumentRepository(db)
    document = await doc_repo.get_by_id(document_id, current_user.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    llm_provider = body.llm_provider or settings.CLASSIFIER_LLM_PROVIDER
    llm_model = body.llm_model or settings.CLASSIFIER_LLM_MODEL
    batch_size = body.batch_size or 10
    batch_overlap = body.batch_overlap or 3

    repo = ClassificationRunRepository(db)
    run = await repo.create(ClassificationRunCreate(
        parse_run_id=body.parse_run_id,
        document_id=document_id,
        labels_requested=body.labels,
        llm_provider=llm_provider,
        llm_model=llm_model,
        batch_size=batch_size,
        batch_overlap=batch_overlap,
    ))

    byok_provider = _classification_provider_to_byok(llm_provider)
    api_key: str | None = None
    if byok_provider:
        provider_key_repo = ProviderKeyRepository(db)
        api_key = await resolve_api_key(provider_key_repo, current_user.id, byok_provider)

    background_tasks.add_task(
        _run_classification_background,
        run_id=run.id,
        parse_run_id=body.parse_run_id,
        labels=body.labels,
        llm_provider=llm_provider,
        llm_model=llm_model,
        batch_size=batch_size,
        batch_overlap=batch_overlap,
        api_key=api_key,
    )

    return _to_run_response(run)


@documents_router.get(
    "/{document_id}/classification-runs",
    response_model=list[ClassificationRunResponse],
)
async def list_document_classification_runs(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    doc_repo = DocumentRepository(db)
    document = await doc_repo.get_by_id(document_id, current_user.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    repo = ClassificationRunRepository(db)
    runs = await repo.list_for_document(document_id)
    return [_to_run_response(r) for r in runs]


@runs_router.get("", response_model=list[ClassificationRunResponse])
async def list_all_classification_runs(
    project_id: UUID = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ClassificationRunRepository(db)
    runs = await repo.list_for_project(project_id)
    return [_to_run_response(r) for r in runs]


@runs_router.get("/{run_id}", response_model=ClassificationRunResponse)
async def get_classification_run(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ClassificationRunRepository(db)
    run = await repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Classification run not found")
    regions = await repo.get_regions(run_id)
    return _to_run_response(run, regions)


@runs_router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_classification_run(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ClassificationRunRepository(db)
    run = await repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Classification run not found")
    await repo.delete(run_id)


@runs_router.get("/{run_id}/blocks", response_model=list[AnnotatedBlockResponse])
async def get_classification_run_blocks(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ClassificationRunRepository(db)
    run = await repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Classification run not found")
    blocks = await repo.get_annotated_blocks(run_id)
    return [
        AnnotatedBlockResponse(
            blockId=b.block_id,
            pageIndex=b.page_index,
            role=b.role,
            text=b.text,
            markdown=b.markdown,
            label=b.label,
        )
        for b in blocks
    ]
