import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, AuthProvider
from app.models.project import Project
from app.models.index import Index, IndexStatus
from app.models.golden_set import GoldenSet, GoldenSetStatus
from app.models.eval_run import EvalRun, EvalRunStatus
from app.models.experiment import Experiment, ExperimentStatus
from app.repositories.experiment_repository import ExperimentRepository
from app.repositories.eval_run_repository import EvalRunRepository
from app.schemas.experiment import ExperimentCreate, ExperimentUpdate
from app.services.experiment_service import ExperimentService
from app.services.exceptions import NotFoundError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def test_user(test_db: AsyncSession) -> User:
    user = User(
        email="testuser@example.com",
        full_name="Test User",
        password_hash="hashed",
        auth_provider=AuthProvider.email,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
async def test_project(test_db: AsyncSession, test_user: User) -> Project:
    project = Project(user_id=test_user.id, name="Test Project")
    test_db.add(project)
    await test_db.commit()
    await test_db.refresh(project)
    return project


@pytest.fixture
async def test_index(test_db: AsyncSession, test_project: Project, test_user: User) -> Index:
    index = Index(
        project_id=test_project.id,
        name="Test Index",
        config={"chunkingStrategy": "recursive_character", "chunkSize": 512},
        status=IndexStatus.ready,
        created_by=test_user.id,
    )
    test_db.add(index)
    await test_db.commit()
    await test_db.refresh(index)
    return index


@pytest.fixture
async def another_index(test_db: AsyncSession, test_project: Project, test_user: User) -> Index:
    index = Index(
        project_id=test_project.id,
        name="Another Index",
        config={"chunkingStrategy": "fixed_size", "chunkSize": 256},
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
        name="Test Golden Set",
        status=GoldenSetStatus.draft,
        created_by=test_user.id,
    )
    test_db.add(gs)
    await test_db.commit()
    await test_db.refresh(gs)
    return gs


@pytest.fixture
def experiment_repo(test_db: AsyncSession) -> ExperimentRepository:
    return ExperimentRepository(test_db)


@pytest.fixture
def eval_run_repo(test_db: AsyncSession) -> EvalRunRepository:
    return EvalRunRepository(test_db)


@pytest.fixture
def experiment_service(experiment_repo: ExperimentRepository) -> ExperimentService:
    return ExperimentService(experiment_repo)


async def _make_run(
    repo: EvalRunRepository,
    project: Project,
    gs: GoldenSet,
    index: Index,
    user: User,
    experiment_id=None,
    variant_label=None,
    config=None,
    mode="retrieval_only",
    name="Test Run",
    gen_provider=None,
    gen_model_id=None,
    judge_provider=None,
    judge_model_id=None,
    system_prompt=None,
) -> EvalRun:
    run = await repo.create(
        project_id=project.id,
        golden_set_id=gs.id,
        index_id=index.id,
        name=name,
        config=config or {"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
        user_id=user.id,
        mode=mode,
        experiment_id=experiment_id,
        variant_label=variant_label,
        generation_model_provider=gen_provider,
        generation_model_id=gen_model_id,
        judge_model_provider=judge_provider,
        judge_model_id=judge_model_id,
        system_prompt=system_prompt,
    )
    return run


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_returns_response(
    experiment_service: ExperimentService, test_project: Project, test_user: User
):
    data = ExperimentCreate(name="Test Exp", description="desc")
    resp = await experiment_service.create(test_project.id, test_user.id, data)
    assert resp.id is not None
    assert resp.name == "Test Exp"
    assert resp.description == "desc"
    assert resp.status == "active"
    assert resp.run_count == 0
    assert resp.baseline_run_id is None


@pytest.mark.asyncio
async def test_list_by_project(
    experiment_service: ExperimentService, test_project: Project, test_user: User
):
    await experiment_service.create(
        test_project.id, test_user.id, ExperimentCreate(name="A")
    )
    await experiment_service.create(
        test_project.id, test_user.id, ExperimentCreate(name="B")
    )
    results = await experiment_service.list_by_project(test_project.id)
    assert len(results) == 2
    # run_count populated
    assert all(r.run_count == 0 for r in results)


@pytest.mark.asyncio
async def test_get_detail_found(
    experiment_service: ExperimentService,
    experiment_repo: ExperimentRepository,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    data = ExperimentCreate(name="Detail Test")
    resp = await experiment_service.create(test_project.id, test_user.id, data)

    await _make_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        experiment_id=resp.id, variant_label="v1",
    )

    detail = await experiment_service.get_detail(resp.id, test_project.id)
    assert detail.name == "Detail Test"
    assert len(detail.runs) == 1
    assert detail.runs[0].variant_label == "v1"
    assert detail.variable_diff is not None


@pytest.mark.asyncio
async def test_get_detail_not_found(
    experiment_service: ExperimentService, test_project: Project
):
    with pytest.raises(NotFoundError):
        await experiment_service.get_detail(uuid4(), test_project.id)


@pytest.mark.asyncio
async def test_update_name_and_status(
    experiment_service: ExperimentService, test_project: Project, test_user: User
):
    resp = await experiment_service.create(
        test_project.id, test_user.id, ExperimentCreate(name="Original")
    )
    updated = await experiment_service.update(
        resp.id, test_project.id,
        ExperimentUpdate(name="Updated", status="concluded"),
    )
    assert updated.name == "Updated"
    assert updated.status == "concluded"


@pytest.mark.asyncio
async def test_update_not_found(
    experiment_service: ExperimentService, test_project: Project
):
    with pytest.raises(NotFoundError):
        await experiment_service.update(
            uuid4(), test_project.id, ExperimentUpdate(name="X")
        )


@pytest.mark.asyncio
async def test_delete_success(
    experiment_service: ExperimentService, test_project: Project, test_user: User
):
    resp = await experiment_service.create(
        test_project.id, test_user.id, ExperimentCreate(name="Delete Me")
    )
    await experiment_service.delete(resp.id, test_project.id)
    with pytest.raises(NotFoundError):
        await experiment_service.get_detail(resp.id, test_project.id)


@pytest.mark.asyncio
async def test_delete_not_found(
    experiment_service: ExperimentService, test_project: Project
):
    with pytest.raises(NotFoundError):
        await experiment_service.delete(uuid4(), test_project.id)


# ---------------------------------------------------------------------------
# Variable diff computation tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_variable_diff_no_runs(experiment_service: ExperimentService):
    diff = experiment_service._compute_variable_diff([])
    assert diff.varying == {}
    assert diff.constant == {}


@pytest.mark.asyncio
async def test_compute_variable_diff_one_run(
    experiment_service: ExperimentService,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    run = await _make_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
    )
    # Reload with relationships
    loaded = await eval_run_repo.get_by_id(run.id, test_project.id)
    diff = experiment_service._compute_variable_diff([loaded])
    assert diff.varying == {}
    assert diff.constant == {}


@pytest.mark.asyncio
async def test_compute_variable_diff_same_config(
    experiment_service: ExperimentService,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    run1 = await _make_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        name="Run 1",
    )
    run2 = await _make_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        name="Run 2",
    )
    r1 = await eval_run_repo.get_by_id(run1.id, test_project.id)
    r2 = await eval_run_repo.get_by_id(run2.id, test_project.id)

    diff = experiment_service._compute_variable_diff([r1, r2])
    assert diff.varying == {}
    assert len(diff.constant) > 0
    assert diff.constant["searchType"] == "semantic"
    assert diff.constant["topK"] == "5"


@pytest.mark.asyncio
async def test_compute_variable_diff_different_index(
    experiment_service: ExperimentService,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    another_index: Index,
    test_user: User,
):
    run1 = await eval_run_repo.create(
        project_id=test_project.id,
        golden_set_id=test_golden_set.id,
        index_id=test_index.id,
        name="Run 1",
        config={"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
        user_id=test_user.id,
    )
    run2 = await eval_run_repo.create(
        project_id=test_project.id,
        golden_set_id=test_golden_set.id,
        index_id=another_index.id,
        name="Run 2",
        config={"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
        user_id=test_user.id,
    )
    r1 = await eval_run_repo.get_by_id(run1.id, test_project.id)
    r2 = await eval_run_repo.get_by_id(run2.id, test_project.id)

    diff = experiment_service._compute_variable_diff([r1, r2])
    assert "index" in diff.varying
    assert len(diff.varying["index"]) == 2
    assert "searchType" not in diff.varying


@pytest.mark.asyncio
async def test_compute_variable_diff_different_search_type(
    experiment_service: ExperimentService,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    run1 = await _make_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        name="Semantic", config={"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
    )
    run2 = await _make_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        name="Hybrid", config={"searchType": "hybrid", "topK": 5, "similarityThreshold": 0},
    )
    r1 = await eval_run_repo.get_by_id(run1.id, test_project.id)
    r2 = await eval_run_repo.get_by_id(run2.id, test_project.id)

    diff = experiment_service._compute_variable_diff([r1, r2])
    assert "searchType" in diff.varying
    assert set(diff.varying["searchType"]) == {"semantic", "hybrid"}


@pytest.mark.asyncio
async def test_compute_variable_diff_different_topk(
    experiment_service: ExperimentService,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    run1 = await _make_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        name="K5", config={"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
    )
    run2 = await _make_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        name="K10", config={"searchType": "semantic", "topK": 10, "similarityThreshold": 0},
    )
    r1 = await eval_run_repo.get_by_id(run1.id, test_project.id)
    r2 = await eval_run_repo.get_by_id(run2.id, test_project.id)

    diff = experiment_service._compute_variable_diff([r1, r2])
    assert "topK" in diff.varying
    assert set(diff.varying["topK"]) == {"5", "10"}


@pytest.mark.asyncio
async def test_compute_variable_diff_different_mode(
    experiment_service: ExperimentService,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    run1 = await _make_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        name="Retrieval", mode="retrieval_only",
    )
    run2 = await _make_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        name="Answer", mode="retrieval_and_answer",
    )
    r1 = await eval_run_repo.get_by_id(run1.id, test_project.id)
    r2 = await eval_run_repo.get_by_id(run2.id, test_project.id)

    diff = experiment_service._compute_variable_diff([r1, r2])
    assert "mode" in diff.varying


@pytest.mark.asyncio
async def test_compute_variable_diff_different_models(
    experiment_service: ExperimentService,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    run1 = await _make_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        name="GPT", gen_provider="openai", gen_model_id="gpt-4o",
    )
    run2 = await _make_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        name="Claude", gen_provider="anthropic", gen_model_id="claude-3-haiku",
    )
    r1 = await eval_run_repo.get_by_id(run1.id, test_project.id)
    r2 = await eval_run_repo.get_by_id(run2.id, test_project.id)

    diff = experiment_service._compute_variable_diff([r1, r2])
    assert "generationModel" in diff.varying


@pytest.mark.asyncio
async def test_compute_variable_diff_multiple_fields_vary(
    experiment_service: ExperimentService,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    another_index: Index,
    test_user: User,
):
    run1 = await eval_run_repo.create(
        project_id=test_project.id,
        golden_set_id=test_golden_set.id,
        index_id=test_index.id,
        name="Run 1",
        config={"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
        user_id=test_user.id,
    )
    run2 = await eval_run_repo.create(
        project_id=test_project.id,
        golden_set_id=test_golden_set.id,
        index_id=another_index.id,
        name="Run 2",
        config={"searchType": "hybrid", "topK": 10, "similarityThreshold": 0},
        user_id=test_user.id,
    )
    r1 = await eval_run_repo.get_by_id(run1.id, test_project.id)
    r2 = await eval_run_repo.get_by_id(run2.id, test_project.id)

    diff = experiment_service._compute_variable_diff([r1, r2])
    assert "index" in diff.varying
    assert "searchType" in diff.varying
    assert "topK" in diff.varying
    # Fields that didn't change should be in constant
    assert "mode" in diff.constant
    assert "similarityThreshold" in diff.constant
