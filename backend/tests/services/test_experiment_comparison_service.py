from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.experiment_service import ExperimentService
from app.services.exceptions import NotFoundError


@pytest.fixture
def mock_repo():
    return AsyncMock()


@pytest.fixture
def service(mock_repo):
    return ExperimentService(mock_repo)


def _make_result(query_id, query_text, precision, recall, f1):
    res = MagicMock()
    res.query_id = query_id
    res.precision = precision
    res.recall = recall
    res.f1 = f1
    res.query = MagicMock()
    res.query.query_text = query_text
    return res


def _make_run(run_id, name, variant_label, status_value, avg_f1, results):
    from app.models.eval_run import EvalRunStatus
    run = MagicMock()
    run.id = run_id
    run.name = name
    run.variant_label = variant_label
    run.status = EvalRunStatus(status_value)
    run.metrics = {"avgF1": avg_f1} if avg_f1 is not None else None
    run.results = results
    return run


def _make_experiment(exp_id, project_id, name, baseline_run_id, runs):
    exp = MagicMock()
    exp.id = exp_id
    exp.project_id = project_id
    exp.name = name
    exp.baseline_run_id = baseline_run_id
    exp.runs = runs
    return exp


@pytest.mark.asyncio
async def test_compare_not_found_raises(service, mock_repo):
    mock_repo.get_for_comparison.return_value = None
    with pytest.raises(NotFoundError):
        await service.compare(uuid4(), uuid4())


@pytest.mark.asyncio
async def test_compare_returns_only_completed_runs(service, mock_repo):
    exp_id = uuid4()
    project_id = uuid4()
    qid = uuid4()

    pending_run = _make_run(uuid4(), "Pending", None, "pending", None, [])
    completed_run = _make_run(
        uuid4(), "Done", "v1", "completed", 0.8,
        [_make_result(qid, "What is X?", 0.9, 0.7, 0.8)]
    )
    exp = _make_experiment(exp_id, project_id, "My Exp", completed_run.id, [pending_run, completed_run])
    mock_repo.get_for_comparison.return_value = exp

    response = await service.compare(exp_id, project_id)

    assert len(response.runs) == 1
    assert response.runs[0].name == "Done"


@pytest.mark.asyncio
async def test_compare_baseline_is_first(service, mock_repo):
    exp_id = uuid4()
    project_id = uuid4()
    baseline_id = uuid4()
    challenger_id = uuid4()
    qid = uuid4()

    baseline = _make_run(
        baseline_id, "Baseline", None, "completed", 0.6,
        [_make_result(qid, "Q1", 0.6, 0.6, 0.6)]
    )
    challenger = _make_run(
        challenger_id, "Challenger", "top_k=10", "completed", 0.8,
        [_make_result(qid, "Q1", 0.8, 0.8, 0.8)]
    )
    exp = _make_experiment(exp_id, project_id, "Exp", baseline_id, [challenger, baseline])
    mock_repo.get_for_comparison.return_value = exp

    response = await service.compare(exp_id, project_id)

    assert response.runs[0].id == baseline_id


@pytest.mark.asyncio
async def test_compare_delta_computed_vs_baseline(service, mock_repo):
    exp_id = uuid4()
    project_id = uuid4()
    baseline_id = uuid4()
    challenger_id = uuid4()
    qid = uuid4()

    baseline = _make_run(
        baseline_id, "Baseline", None, "completed", 0.6,
        [_make_result(qid, "Q1", 0.6, 0.6, 0.6)]
    )
    challenger = _make_run(
        challenger_id, "Challenger", "v2", "completed", 0.8,
        [_make_result(qid, "Q1", 0.8, 0.8, 0.8)]
    )
    exp = _make_experiment(exp_id, project_id, "Exp", baseline_id, [baseline, challenger])
    mock_repo.get_for_comparison.return_value = exp

    response = await service.compare(exp_id, project_id)

    assert len(response.rows) == 1
    row = response.rows[0]
    baseline_metrics = row.results[str(baseline_id)]
    challenger_metrics = row.results[str(challenger_id)]
    assert baseline_metrics.delta_f1 is None
    assert round(challenger_metrics.delta_f1, 4) == round(0.8 - 0.6, 4)


@pytest.mark.asyncio
async def test_compare_missing_result_for_run(service, mock_repo):
    """Run with no result for a query should be absent from that row's results dict."""
    exp_id = uuid4()
    project_id = uuid4()
    baseline_id = uuid4()
    challenger_id = uuid4()
    q1 = uuid4()
    q2 = uuid4()

    baseline = _make_run(
        baseline_id, "Baseline", None, "completed", 0.6,
        [_make_result(q1, "Q1", 0.6, 0.6, 0.6), _make_result(q2, "Q2", 0.5, 0.5, 0.5)]
    )
    challenger = _make_run(
        challenger_id, "Challenger", "v2", "completed", 0.8,
        [_make_result(q1, "Q1", 0.8, 0.8, 0.8)]  # no result for q2
    )
    exp = _make_experiment(exp_id, project_id, "Exp", baseline_id, [baseline, challenger])
    mock_repo.get_for_comparison.return_value = exp

    response = await service.compare(exp_id, project_id)

    assert len(response.rows) == 2
    q2_row = next(r for r in response.rows if r.query_id == q2)
    assert str(challenger_id) not in q2_row.results
