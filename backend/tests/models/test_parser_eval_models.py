import pytest
from uuid import uuid4
from app.models.parser_eval import (
    ParserEvalCase, ParserEvalDataset, ParserEvalDatasetCase,
    ParserEvalRun, ParserEvalResult,
    ParserEvalDimension, ParserEvalSourceMethod, ParserEvalReviewStatus,
    ParserEvalRunStatus,
)


@pytest.mark.asyncio
async def test_case_defaults_and_persist(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    case = ParserEvalCase(
        project_id=project_id, source_document_id=source_id,
        dimension=ParserEvalDimension.text, expected={"pages": ["hi"]},
        created_by=user_id)
    test_db.add(case)
    await test_db.commit()
    await test_db.refresh(case)
    assert case.source_method == ParserEvalSourceMethod.human
    assert case.review_status == ParserEvalReviewStatus.draft


@pytest.mark.asyncio
async def test_dataset_membership(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    case = ParserEvalCase(project_id=project_id, source_document_id=source_id,
                          dimension=ParserEvalDimension.text, expected={"pages": ["x"]},
                          created_by=user_id)
    ds = ParserEvalDataset(project_id=project_id, name="smoke", created_by=user_id)
    test_db.add_all([case, ds])
    await test_db.commit()
    test_db.add(ParserEvalDatasetCase(dataset_id=ds.id, eval_case_id=case.id))
    await test_db.commit()
    await test_db.refresh(ds)
    assert [c.id for c in ds.cases] == [case.id]


@pytest.mark.asyncio
async def test_run_and_result_shapes(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    run = ParserEvalRun(project_id=project_id, name="r",
                        variants=[{"adapter": "docling", "config": {}}],
                        eval_case_ids=[], created_by=user_id)
    case = ParserEvalCase(project_id=project_id, source_document_id=source_id,
                          dimension=ParserEvalDimension.text, expected={"pages": ["x"]},
                          created_by=user_id)
    test_db.add_all([run, case])
    await test_db.commit()
    result = ParserEvalResult(
        run_id=run.id, eval_case_id=case.id, adapter="docling", config={},
        variant_key="docling@abc123", metrics={"similarity": 0.9}, primary_metric="similarity",
        details={"per_page": []}, cost={"usd": 0.0}, latency_ms=120)
    test_db.add(result)
    await test_db.commit()
    await test_db.refresh(result)
    assert result.metrics["similarity"] == 0.9
    assert run.status == ParserEvalRunStatus.pending
