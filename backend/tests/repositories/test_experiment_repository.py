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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def experiment_repo(test_db: AsyncSession) -> ExperimentRepository:
    return ExperimentRepository(test_db)


@pytest.fixture
def eval_run_repo(test_db: AsyncSession) -> EvalRunRepository:
    return EvalRunRepository(test_db)


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
    project = Project(
        user_id=test_user.id,
        name="Test Project",
    )
    test_db.add(project)
    await test_db.commit()
    await test_db.refresh(project)
    return project


@pytest.fixture
async def another_project(test_db: AsyncSession, test_user: User) -> Project:
    project = Project(
        user_id=test_user.id,
        name="Another Project",
    )
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
async def test_golden_set(
    test_db: AsyncSession, test_project: Project, test_user: User
) -> GoldenSet:
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


async def _create_eval_run(
    eval_run_repo: EvalRunRepository,
    project: Project,
    golden_set: GoldenSet,
    index: Index,
    user: User,
    name: str = "Test Run",
    experiment_id=None,
    variant_label=None,
    config=None,
    mode="retrieval_only",
) -> EvalRun:
    return await eval_run_repo.create(
        project_id=project.id,
        golden_set_id=golden_set.id,
        index_id=index.id,
        name=name,
        config=config or {"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
        user_id=user.id,
        mode=mode,
        experiment_id=experiment_id,
        variant_label=variant_label,
    )


# ---------------------------------------------------------------------------
# Experiment CRUD tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_experiment(
    experiment_repo: ExperimentRepository, test_project: Project, test_user: User
):
    exp = await experiment_repo.create(
        project_id=test_project.id,
        name="Hypothesis A",
        user_id=test_user.id,
        description="Does X improve Y?",
    )
    assert exp.id is not None
    assert exp.name == "Hypothesis A"
    assert exp.description == "Does X improve Y?"
    assert exp.project_id == test_project.id
    assert exp.created_by == test_user.id
    assert exp.status == ExperimentStatus.active
    assert exp.baseline_run_id is None
    assert exp.notes is None
    assert exp.created_at is not None
    assert exp.updated_at is not None


@pytest.mark.asyncio
async def test_create_experiment_minimal(
    experiment_repo: ExperimentRepository, test_project: Project, test_user: User
):
    exp = await experiment_repo.create(
        project_id=test_project.id,
        name="Minimal",
        user_id=test_user.id,
    )
    assert exp.name == "Minimal"
    assert exp.description is None


@pytest.mark.asyncio
async def test_get_by_id_found(
    experiment_repo: ExperimentRepository, test_project: Project, test_user: User
):
    exp = await experiment_repo.create(
        project_id=test_project.id,
        name="Find Me",
        user_id=test_user.id,
    )
    found = await experiment_repo.get_by_id(exp.id, test_project.id)
    assert found is not None
    assert found.id == exp.id
    assert found.name == "Find Me"


@pytest.mark.asyncio
async def test_get_by_id_not_found(
    experiment_repo: ExperimentRepository, test_project: Project
):
    found = await experiment_repo.get_by_id(uuid4(), test_project.id)
    assert found is None


@pytest.mark.asyncio
async def test_get_by_id_wrong_project(
    experiment_repo: ExperimentRepository,
    test_project: Project,
    another_project: Project,
    test_user: User,
):
    exp = await experiment_repo.create(
        project_id=test_project.id,
        name="Wrong Project",
        user_id=test_user.id,
    )
    found = await experiment_repo.get_by_id(exp.id, another_project.id)
    assert found is None


@pytest.mark.asyncio
async def test_list_by_project(
    experiment_repo: ExperimentRepository, test_project: Project, test_user: User
):
    await experiment_repo.create(
        project_id=test_project.id, name="First", user_id=test_user.id
    )
    await experiment_repo.create(
        project_id=test_project.id, name="Second", user_id=test_user.id
    )
    experiments = await experiment_repo.list_by_project(test_project.id)
    assert len(experiments) == 2
    # Ordered by created_at desc
    assert experiments[0].name == "Second"
    assert experiments[1].name == "First"


@pytest.mark.asyncio
async def test_list_by_project_empty(
    experiment_repo: ExperimentRepository, test_project: Project
):
    experiments = await experiment_repo.list_by_project(test_project.id)
    assert experiments == []


@pytest.mark.asyncio
async def test_list_by_project_scoped(
    experiment_repo: ExperimentRepository,
    test_project: Project,
    another_project: Project,
    test_user: User,
):
    await experiment_repo.create(
        project_id=test_project.id, name="Project A", user_id=test_user.id
    )
    await experiment_repo.create(
        project_id=another_project.id, name="Project B", user_id=test_user.id
    )
    results = await experiment_repo.list_by_project(test_project.id)
    assert len(results) == 1
    assert results[0].name == "Project A"


@pytest.mark.asyncio
async def test_update_name(
    experiment_repo: ExperimentRepository, test_project: Project, test_user: User
):
    exp = await experiment_repo.create(
        project_id=test_project.id, name="Original", user_id=test_user.id
    )
    updated = await experiment_repo.update(exp.id, test_project.id, name="Updated")
    assert updated is not None
    assert updated.name == "Updated"


@pytest.mark.asyncio
async def test_update_status(
    experiment_repo: ExperimentRepository, test_project: Project, test_user: User
):
    exp = await experiment_repo.create(
        project_id=test_project.id, name="Active", user_id=test_user.id
    )
    updated = await experiment_repo.update(
        exp.id, test_project.id, status=ExperimentStatus.concluded
    )
    assert updated is not None
    assert updated.status == ExperimentStatus.concluded


@pytest.mark.asyncio
async def test_update_notes(
    experiment_repo: ExperimentRepository, test_project: Project, test_user: User
):
    exp = await experiment_repo.create(
        project_id=test_project.id, name="Notes Test", user_id=test_user.id
    )
    updated = await experiment_repo.update(
        exp.id, test_project.id, notes="Some conclusions"
    )
    assert updated is not None
    assert updated.notes == "Some conclusions"


@pytest.mark.asyncio
async def test_update_baseline_run_id(
    experiment_repo: ExperimentRepository,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    exp = await experiment_repo.create(
        project_id=test_project.id, name="Baseline Test", user_id=test_user.id
    )
    run = await _create_eval_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        experiment_id=exp.id,
    )
    updated = await experiment_repo.update(
        exp.id, test_project.id, baseline_run_id=run.id
    )
    assert updated is not None
    assert updated.baseline_run_id == run.id


@pytest.mark.asyncio
async def test_update_not_found(
    experiment_repo: ExperimentRepository, test_project: Project
):
    result = await experiment_repo.update(uuid4(), test_project.id, name="Nope")
    assert result is None


@pytest.mark.asyncio
async def test_delete_experiment(
    experiment_repo: ExperimentRepository, test_project: Project, test_user: User
):
    exp = await experiment_repo.create(
        project_id=test_project.id, name="Delete Me", user_id=test_user.id
    )
    deleted = await experiment_repo.delete(exp.id, test_project.id)
    assert deleted is True
    found = await experiment_repo.get_by_id(exp.id, test_project.id)
    assert found is None


@pytest.mark.asyncio
async def test_delete_unlinks_runs(
    experiment_repo: ExperimentRepository,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    exp = await experiment_repo.create(
        project_id=test_project.id, name="Unlink Test", user_id=test_user.id
    )
    run = await _create_eval_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        experiment_id=exp.id, variant_label="variant A",
    )
    await experiment_repo.delete(exp.id, test_project.id)

    # Reload the run and check it's unlinked
    reloaded = await eval_run_repo.get_by_id(run.id, test_project.id)
    assert reloaded is not None
    assert reloaded.experiment_id is None
    assert reloaded.variant_label is None


@pytest.mark.asyncio
async def test_delete_not_found(
    experiment_repo: ExperimentRepository, test_project: Project
):
    deleted = await experiment_repo.delete(uuid4(), test_project.id)
    assert deleted is False


@pytest.mark.asyncio
async def test_get_run_count(
    experiment_repo: ExperimentRepository,
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    exp = await experiment_repo.create(
        project_id=test_project.id, name="Count Test", user_id=test_user.id
    )
    await _create_eval_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        name="Run 1", experiment_id=exp.id,
    )
    await _create_eval_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        name="Run 2", experiment_id=exp.id,
    )
    count = await experiment_repo.get_run_count(exp.id)
    assert count == 2


@pytest.mark.asyncio
async def test_get_run_count_zero(
    experiment_repo: ExperimentRepository, test_project: Project, test_user: User
):
    exp = await experiment_repo.create(
        project_id=test_project.id, name="Empty", user_id=test_user.id
    )
    count = await experiment_repo.get_run_count(exp.id)
    assert count == 0


# ---------------------------------------------------------------------------
# EvalRun experiment fields tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_run_with_experiment_id(
    eval_run_repo: EvalRunRepository,
    experiment_repo: ExperimentRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    exp = await experiment_repo.create(
        project_id=test_project.id, name="Linked", user_id=test_user.id
    )
    run = await _create_eval_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        experiment_id=exp.id, variant_label="topK=10",
    )
    assert run.experiment_id == exp.id
    assert run.variant_label == "topK=10"


@pytest.mark.asyncio
async def test_create_run_without_experiment_id(
    eval_run_repo: EvalRunRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    run = await _create_eval_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
    )
    assert run.experiment_id is None
    assert run.variant_label is None


@pytest.mark.asyncio
async def test_get_by_id_loads_experiment(
    eval_run_repo: EvalRunRepository,
    experiment_repo: ExperimentRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    exp = await experiment_repo.create(
        project_id=test_project.id, name="Eager Load", user_id=test_user.id
    )
    run = await _create_eval_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        experiment_id=exp.id,
    )
    loaded = await eval_run_repo.get_by_id(run.id, test_project.id)
    assert loaded is not None
    assert loaded.experiment is not None
    assert loaded.experiment.name == "Eager Load"


@pytest.mark.asyncio
async def test_list_by_project_loads_experiment(
    eval_run_repo: EvalRunRepository,
    experiment_repo: ExperimentRepository,
    test_project: Project,
    test_golden_set: GoldenSet,
    test_index: Index,
    test_user: User,
):
    exp = await experiment_repo.create(
        project_id=test_project.id, name="List Load", user_id=test_user.id
    )
    await _create_eval_run(
        eval_run_repo, test_project, test_golden_set, test_index, test_user,
        experiment_id=exp.id,
    )
    runs = await eval_run_repo.list_by_project(test_project.id)
    assert len(runs) == 1
    assert runs[0].experiment is not None
    assert runs[0].experiment.name == "List Load"
