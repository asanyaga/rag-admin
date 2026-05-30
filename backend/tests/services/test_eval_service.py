"""Tests for EvalService — experiment-related functionality."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, AuthProvider
from app.models.project import Project
from app.models.index import Index, IndexStatus
from app.models.golden_set import GoldenSet, GoldenSetStatus, GoldenSetQuery, SourceMethod, ReviewStatus
from app.models.experiment import Experiment, ExperimentStatus
from app.repositories.eval_run_repository import EvalRunRepository
from app.repositories.golden_set_repository import GoldenSetRepository
from app.repositories.experiment_repository import ExperimentRepository
from app.schemas.eval_run import EvalRunConfig
from app.schemas.query import QueryResponse, RetrievalResult, RetrievalResultMetadata
from app.services.eval_service import EvalService
from app.services.exceptions import NotFoundError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def test_user(test_db: AsyncSession) -> User:
    user = User(
        email="evaltest@example.com",
        full_name="Eval Test User",
        password_hash="hashed",
        auth_provider=AuthProvider.email,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
async def test_project(test_db: AsyncSession, test_user: User) -> Project:
    project = Project(user_id=test_user.id, name="Eval Project")
    test_db.add(project)
    await test_db.commit()
    await test_db.refresh(project)
    return project


@pytest.fixture
async def test_index(test_db: AsyncSession, test_project: Project, test_user: User) -> Index:
    index = Index(
        project_id=test_project.id,
        name="Eval Index",
        config={"chunkingStrategy": "recursive_character", "chunkSize": 512},
        status=IndexStatus.ready,
        created_by=test_user.id,
    )
    test_db.add(index)
    await test_db.commit()
    await test_db.refresh(index)
    return index


@pytest.fixture
async def test_golden_set(test_db: AsyncSession, test_project: Project, test_user: User) -> GoldenSet:
    gs = GoldenSet(
        project_id=test_project.id,
        name="Eval Golden Set",
        status=GoldenSetStatus.draft,
        created_by=test_user.id,
    )
    test_db.add(gs)
    await test_db.commit()
    await test_db.refresh(gs)
    # Add a query so the golden set is usable
    query = GoldenSetQuery(
        golden_set_id=gs.id,
        query_text="What is RAG?",
        source_method=SourceMethod.manual,
        review_status=ReviewStatus.accepted,
    )
    test_db.add(query)
    await test_db.commit()
    return gs


@pytest.fixture
async def test_experiment(
    test_db: AsyncSession, test_project: Project, test_user: User
) -> Experiment:
    exp = Experiment(
        project_id=test_project.id,
        name="Eval Experiment",
        created_by=test_user.id,
    )
    test_db.add(exp)
    await test_db.commit()
    await test_db.refresh(exp)
    return exp


@pytest.fixture
def eval_run_repo(test_db: AsyncSession) -> EvalRunRepository:
    return EvalRunRepository(test_db)


@pytest.fixture
def golden_set_repo(test_db: AsyncSession) -> GoldenSetRepository:
    return GoldenSetRepository(test_db)


@pytest.fixture
def eval_service(eval_run_repo, golden_set_repo) -> EvalService:
    # No query_service needed for these tests (CRUD only)
    return EvalService(eval_run_repo, golden_set_repo, query_service=None)


# ---------------------------------------------------------------------------
# get_run_config tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_run_config(
    eval_service: EvalService,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
    test_experiment: Experiment,
):
    run = await eval_run_repo.create(
        project_id=test_project.id,
        golden_set_id=test_golden_set.id,
        index_id=test_index.id,
        name="Config Run",
        config={"searchType": "hybrid", "topK": 10, "similarityThreshold": 0.3},
        user_id=test_user.id,
        mode="retrieval_and_answer",
        generation_config={
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.2,
            "max_tokens": 2048,
            "system_prompt": "Custom prompt",
        },
        judge_config={
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
        },
        experiment_id=test_experiment.id,
        variant_label="hybrid k=10",
    )

    config = await eval_service.get_run_config(run.id, test_project.id)

    assert config["goldenSetId"] == str(test_golden_set.id)
    assert config["indexId"] == str(test_index.id)
    assert config["name"] == "Config Run"
    assert config["config"]["searchType"] == "hybrid"
    assert config["config"]["topK"] == 10
    assert config["config"]["similarityThreshold"] == 0.3
    assert config["mode"] == "retrieval_and_answer"
    assert config["generationConfig"]["provider"] == "openai"
    assert config["generationConfig"]["model"] == "gpt-4o"
    assert config["generationConfig"]["system_prompt"] == "Custom prompt"
    assert config["judgeConfig"]["provider"] == "anthropic"
    assert config["judgeConfig"]["model"] == "claude-sonnet-4-6"
    assert config["experimentId"] == str(test_experiment.id)
    assert config["variantLabel"] == "hybrid k=10"


@pytest.mark.asyncio
async def test_get_run_config_retrieval_only(
    eval_service: EvalService,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    run = await eval_run_repo.create(
        project_id=test_project.id,
        golden_set_id=test_golden_set.id,
        index_id=test_index.id,
        name="Simple Run",
        config={"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
        user_id=test_user.id,
    )

    config = await eval_service.get_run_config(run.id, test_project.id)

    assert config["mode"] == "retrieval_only"
    assert config["generationConfig"] is None
    assert config["judgeConfig"] is None
    assert config["experimentId"] is None
    assert config["variantLabel"] is None


@pytest.mark.asyncio
async def test_get_run_config_not_found(
    eval_service: EvalService, test_project: Project
):
    with pytest.raises(NotFoundError):
        await eval_service.get_run_config(uuid4(), test_project.id)


# ---------------------------------------------------------------------------
# _to_response experiment fields tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_to_response_includes_experiment_name(
    eval_service: EvalService,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
    test_experiment: Experiment,
):
    run = await eval_run_repo.create(
        project_id=test_project.id,
        golden_set_id=test_golden_set.id,
        index_id=test_index.id,
        name="Linked Run",
        config={"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
        user_id=test_user.id,
        experiment_id=test_experiment.id,
        variant_label="v1",
    )
    loaded = await eval_run_repo.get_by_id(run.id, test_project.id)
    resp = eval_service._to_response(loaded)

    assert resp.experiment_id == test_experiment.id
    assert resp.experiment_name == "Eval Experiment"
    assert resp.variant_label == "v1"


@pytest.mark.asyncio
async def test_to_response_no_experiment(
    eval_service: EvalService,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    run = await eval_run_repo.create(
        project_id=test_project.id,
        golden_set_id=test_golden_set.id,
        index_id=test_index.id,
        name="Standalone Run",
        config={"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
        user_id=test_user.id,
    )
    loaded = await eval_run_repo.get_by_id(run.id, test_project.id)
    resp = eval_service._to_response(loaded)

    assert resp.experiment_id is None
    assert resp.experiment_name is None
    assert resp.variant_label is None


# ---------------------------------------------------------------------------
# _process_single_query metric calculation tests
# ---------------------------------------------------------------------------

def _make_query_service_mock(doc_id: str, page_numbers: list[int]):
    """Return a mock query_service whose query_index returns one chunk on the given pages."""
    meta = RetrievalResultMetadata(
        documentId=doc_id,
        documentName="test.pdf",
        page=page_numbers[0] if page_numbers else None,
        pageNumbers=page_numbers or None,
        chunkIndex=0,
        tokenCount=50,
        charCount=200,
    )
    result = RetrievalResult(
        chunkId="chunk-1",
        rank=1,
        score=0.9,
        content="relevant content",
        metadata=meta,
    )
    response = QueryResponse(
        query="test query",
        results=[result],
        totalResults=1,
        searchType="semantic",
        executionTimeMs=10.0,
    )
    mock_qs = MagicMock()
    mock_qs.query_index = AsyncMock(return_value=response)
    return mock_qs


def _make_eval_service_for_metric_test(eval_run_repo, golden_set_repo, doc_id, page_numbers):
    """Build an EvalService with mocked query_service and mocked create_result.

    create_result is mocked to avoid a DB insert with a dangling FK —
    these tests are purely about the metric calculation, not persistence.
    """
    query_service = _make_query_service_mock(doc_id=doc_id, page_numbers=page_numbers)
    svc = EvalService(eval_run_repo, golden_set_repo, query_service=query_service)
    svc.eval_repo.create_result = AsyncMock()
    return svc


def _make_run_stub(test_index, test_project, test_user):
    run = MagicMock()
    run.index_id = test_index.id
    run.project_id = test_project.id
    run.created_by = test_user.id
    run.mode = "retrieval_only"
    run.generation_config = None
    run.judge_config = None
    return run


def _make_query_stub(doc_id: str, pages: list[int]):
    source = MagicMock()
    source.document_id = doc_id   # str; service calls str() on it
    source.locator = {"type": "page", "pages": pages}
    query = MagicMock()
    query.id = uuid4()
    query.query_text = "test query"
    query.sources = [source]
    return query


@pytest.mark.asyncio
async def test_process_single_query_returns_nonzero_metrics_when_pages_match(
    eval_run_repo, golden_set_repo, test_project, test_index, test_user
):
    """When chunk page_numbers overlap the golden set source locator, metrics must be > 0."""
    doc_id = str(uuid4())
    svc = _make_eval_service_for_metric_test(eval_run_repo, golden_set_repo, doc_id, page_numbers=[2])
    run = _make_run_stub(test_index, test_project, test_user)
    query = _make_query_stub(doc_id=doc_id, pages=[2])
    config = EvalRunConfig(searchType="semantic", topK=5, similarityThreshold=0.0)

    result = await svc._process_single_query(
        run=run, query=query, config=config,
        run_id=uuid4(), user_id=test_user.id, is_answer_mode=False,
    )

    assert result["precision"] > 0, "precision should be non-zero when pages match"
    assert result["recall"] > 0, "recall should be non-zero when pages match"
    assert result["f1"] > 0, "F1 should be non-zero when pages match"


@pytest.mark.asyncio
async def test_process_single_query_returns_zero_metrics_when_chunk_has_no_page_numbers(
    eval_run_repo, golden_set_repo, test_project, test_index, test_user
):
    """When chunk has no page_numbers, metrics must be zero (documents the bug state)."""
    doc_id = str(uuid4())
    svc = _make_eval_service_for_metric_test(eval_run_repo, golden_set_repo, doc_id, page_numbers=[])
    run = _make_run_stub(test_index, test_project, test_user)
    query = _make_query_stub(doc_id=doc_id, pages=[2])
    config = EvalRunConfig(searchType="semantic", topK=5, similarityThreshold=0.0)

    result = await svc._process_single_query(
        run=run, query=query, config=config,
        run_id=uuid4(), user_id=test_user.id, is_answer_mode=False,
    )

    assert result["precision"] == 0.0
    assert result["recall"] == 0.0
    assert result["f1"] == 0.0
